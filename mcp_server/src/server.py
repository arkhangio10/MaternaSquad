"""MaternaSquad MCP Server.

Exposes 10 tools usable by any A2A agent in the squad. SHARP context flows in
via HTTP headers and is parsed once per request.

Run locally:
    python -m mcp_server.src.server

Or with the script:
    .\\scripts\\run_mcp.ps1
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import structlog
from dotenv import load_dotenv
from fastmcp import Context, FastMCP
from fastmcp.server.dependencies import get_http_headers

from mcp_server.src.audit import write_entry
from mcp_server.src.sharp.context import SharpContext
from mcp_server.src.tools.coverage_tools import (
    PaEvidencePacket,
    assemble_pas_shaped_bundle,
    draft_medical_necessity,
    fetch_coverage,
    fetch_service_request,
    predict_denial_risk,
)
from mcp_server.src.tools.escalation_tools import TriageDecision, triage_symptom
from mcp_server.src.tools.fhir_tools import PregnancyContext, get_pregnancy_context
from mcp_server.src.tools.risk_tools import (
    RiskScore,
    gdm_risk,
    preeclampsia_risk,
    preterm_birth_risk,
)
from mcp_server.src.tools.translation_tools import (
    PatientMessage,
    translate_for_patient,
    warning_signs_card,
)

load_dotenv()
log = structlog.get_logger("maternasquad-mcp")


# Prompt Opinion FHIR context extension - declared in our MCP capabilities so
# Po sends `x-fhir-server-url`, `x-fhir-access-token`, and `x-patient-id` HTTP
# headers on every tool call. Without it, Po sends only `x-patient-id` and the
# MCP cannot query the workspace FHIR proxy.
# Spec: https://docs.promptopinion.ai/fhir-context/mcp-fhir-context
PO_FHIR_EXTENSION_ID = "ai.promptopinion/fhir-context"
PO_FHIR_EXTENSION_SCOPES: list[dict[str, Any]] = [
    {"name": "patient/Patient.rs", "required": True},
    {"name": "patient/Condition.rs", "required": True},
    {"name": "patient/Observation.rs", "required": True},
    {"name": "patient/MedicationRequest.rs"},
    {"name": "patient/MedicationStatement.rs"},
    {"name": "patient/Encounter.rs"},
    {"name": "patient/CarePlan.rs"},
    {"name": "patient/DocumentReference.rs"},
    {"name": "patient/ServiceRequest.rs"},
    {"name": "patient/Coverage.rs"},
]

mcp: FastMCP = FastMCP(
    name="maternasquad-mcp",
    instructions="""MaternaSquad MCP server. Tools for maternal-health A2A agents.

All tools require FHIR context, provided either via SHARP headers (X-SHARP-*)
from our internal A2A agents, or via Prompt Opinion's FHIR context extension
(declared in capabilities) which sends x-fhir-server-url, x-fhir-access-token,
and x-patient-id on every tool call.

Synthetic data only. Every clinical output cites FHIR resource references.""",
)


# Monkey-patch FastMCP's low-level server to inject the Po FHIR extension into
# the InitializeResult. The on_initialize middleware hook cannot mutate the
# response because the MCP SDK sends it before middleware sees it; patching
# `get_capabilities` is the documented escape hatch.
_LL_SERVER = mcp._mcp_server
_ORIGINAL_GET_CAPS = _LL_SERVER.get_capabilities


def _patched_get_capabilities(notification_options, experimental_capabilities):  # type: ignore[no-untyped-def]
    caps = _ORIGINAL_GET_CAPS(notification_options, experimental_capabilities)
    existing = getattr(caps, "extensions", None) or {}
    caps.extensions = {
        **existing,
        PO_FHIR_EXTENSION_ID: {"scopes": PO_FHIR_EXTENSION_SCOPES},
    }
    return caps


_LL_SERVER.get_capabilities = _patched_get_capabilities  # type: ignore[method-assign]


def _ctx_from_request_headers(
    headers: dict[str, str] | None, ctx: Context | None = None
) -> SharpContext:
    """Materialize SHARP context with diagnostic logging.

    Resolution order: tool-arg headers, FastMCP Context's HTTP request headers,
    `get_http_headers()`, and finally env-var defaults.
    """
    if headers:
        try:
            return SharpContext.from_headers(headers)
        except ValueError:
            log.info("ctx.from_headers_arg_missing_keys", keys=sorted(headers.keys()))

    ctx_headers: dict[str, str] = {}
    ctx_path = "none"
    if ctx is not None:
        try:
            rc = ctx.request_context
            if rc is not None:
                req = rc.request  # type: ignore[union-attr]
                if req is not None and hasattr(req, "headers"):
                    ctx_headers = dict(req.headers)
                    ctx_path = "ctx.request_context.request.headers"
        except Exception as e:  # noqa: BLE001
            log.warning("ctx.request_access_failed", error=str(e))

    if not ctx_headers:
        try:
            ctx_headers = dict(get_http_headers(include_all=True) or {})
            if ctx_headers:
                ctx_path = "get_http_headers"
        except Exception:  # noqa: BLE001
            ctx_headers = {}

    log.info(
        "ctx.headers_seen",
        source=ctx_path,
        ctx_is_none=ctx is None,
        header_count=len(ctx_headers),
        header_names=sorted(ctx_headers.keys())[:30],
        has_x_patient_id="x-patient-id" in ctx_headers,
        has_x_fhir_server_url="x-fhir-server-url" in ctx_headers,
        has_x_fhir_access_token="x-fhir-access-token" in ctx_headers,
    )

    if ctx_headers:
        try:
            return SharpContext.from_headers(ctx_headers)
        except ValueError as e:
            log.info("ctx.from_headers_validation_failed", reason=str(e))

    # Local dev fallback: env vars seed a context for testing without a real EHR.
    return SharpContext(
        patient_id=os.environ.get("DEV_PATIENT_ID", "example-patient"),
        fhir_server_url=os.environ.get("FHIR_BASE_URL", "http://localhost:8090/fhir"),
        fhir_access_token=os.environ.get("FHIR_ACCESS_TOKEN") or None,
    )


@mcp.tool
async def fhir_get_pregnancy_context(
    headers: dict[str, str] | None = None,
    lookback_days: int = 365,
    mcp_ctx: Context | None = None,
) -> PregnancyContext:
    """Aggregate FHIR resources relevant to a pregnant patient.

    Returns Patient summary, active Conditions, vitals Observations,
    MedicationRequests, CarePlans and recent Encounters with citation refs.
    """
    ctx = _ctx_from_request_headers(headers, ctx=mcp_ctx)
    result = await get_pregnancy_context(ctx, lookback_days=lookback_days)
    write_entry(
        ctx=ctx,
        actor="mcp:fhir_get_pregnancy_context",
        action="aggregate",
        input_summary=f"lookback_days={lookback_days}",
        output_summary=f"resources={len(result.cited_references)}",
        cited_resources=result.cited_references,
    )
    return result


@mcp.tool
async def acog_preeclampsia_risk(
    headers: dict[str, str] | None = None,
    mcp_ctx: Context | None = None,
) -> RiskScore:
    """Compute preeclampsia risk per USPSTF 2021 and ACOG PB 222 (2020)."""
    ctx = _ctx_from_request_headers(headers, ctx=mcp_ctx)
    pregnancy_ctx = await get_pregnancy_context(ctx)
    score = preeclampsia_risk(pregnancy_ctx)
    write_entry(
        ctx=ctx,
        actor="mcp:acog_preeclampsia_risk",
        action="risk_score",
        output_summary=f"level={score.level}",
        cited_resources=score.cited_references,
    )
    return score


@mcp.tool
async def acog_gdm_risk(
    headers: dict[str, str] | None = None,
    mcp_ctx: Context | None = None,
) -> RiskScore:
    """Compute gestational diabetes risk per ACOG PB 234 (2021) + ADA 2024."""
    ctx = _ctx_from_request_headers(headers, ctx=mcp_ctx)
    pregnancy_ctx = await get_pregnancy_context(ctx)
    score = gdm_risk(pregnancy_ctx)
    write_entry(
        ctx=ctx,
        actor="mcp:acog_gdm_risk",
        action="risk_score",
        output_summary=f"level={score.level}",
        cited_resources=score.cited_references,
    )
    return score


@mcp.tool
async def acog_preterm_birth_risk(
    headers: dict[str, str] | None = None,
    mcp_ctx: Context | None = None,
) -> RiskScore:
    """Compute preterm birth risk per ACOG PB 232 (2021)."""
    ctx = _ctx_from_request_headers(headers, ctx=mcp_ctx)
    pregnancy_ctx = await get_pregnancy_context(ctx)
    score = preterm_birth_risk(pregnancy_ctx)
    write_entry(
        ctx=ctx,
        actor="mcp:acog_preterm_birth_risk",
        action="risk_score",
        output_summary=f"level={score.level}",
        cited_resources=score.cited_references,
    )
    return score


@mcp.tool
async def patient_translate_message(
    clinical_summary: str,
    grounded_references: list[str],
    target_grade_level: int = 5,
    headers: dict[str, str] | None = None,
    mcp_ctx: Context | None = None,
) -> PatientMessage:
    """Translate clinical content into patient-friendly text in ctx.locale."""
    ctx = _ctx_from_request_headers(headers, ctx=mcp_ctx)
    msg = await translate_for_patient(
        ctx,
        clinical_summary=clinical_summary,
        grounded_references=grounded_references,
        target_grade_level=target_grade_level,
    )
    write_entry(
        ctx=ctx,
        actor="mcp:patient_translate_message",
        action="translate",
        model_id=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        input_summary=f"locale={ctx.locale}, grade={target_grade_level}",
        output_summary=f"len={len(msg.text)}",
        cited_resources=msg.cited_references,
    )
    return msg


@mcp.tool
async def patient_warning_signs_card(
    condition_focus: str,
    grounded_references: list[str],
    target_grade_level: int = 5,
    headers: dict[str, str] | None = None,
    mcp_ctx: Context | None = None,
) -> PatientMessage:
    """Produce a warning-signs 'when to seek care' card for a condition."""
    ctx = _ctx_from_request_headers(headers, ctx=mcp_ctx)
    msg = await warning_signs_card(
        ctx,
        condition_focus=condition_focus,
        grounded_references=grounded_references,
        target_grade_level=target_grade_level,
    )
    write_entry(
        ctx=ctx,
        actor="mcp:patient_warning_signs_card",
        action="warning_card",
        model_id=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        input_summary=f"condition={condition_focus}, locale={ctx.locale}",
        cited_resources=msg.cited_references,
    )
    return msg


@mcp.tool
async def postpartum_triage(
    patient_message: str,
    pregnancy_context_summary: str,
    grounded_references: list[str],
    headers: dict[str, str] | None = None,
    mcp_ctx: Context | None = None,
) -> TriageDecision:
    """Classify a postpartum symptom message and draft an SBAR escalation.

    Uses CDC Hear Her warning signs and ACOG PB 736.
    """
    ctx = _ctx_from_request_headers(headers, ctx=mcp_ctx)
    decision = await triage_symptom(
        ctx,
        patient_message=patient_message,
        pregnancy_context_summary=pregnancy_context_summary,
        grounded_references=grounded_references,
    )
    write_entry(
        ctx=ctx,
        actor="mcp:postpartum_triage",
        action="triage",
        model_id=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        input_summary=f"urgency={decision.urgency}",
        output_summary=decision.symptom_summary[:120],
        cited_resources=decision.cited_references,
    )
    return decision


@mcp.tool
async def pa_draft_evidence_packet(
    service_request_id: str,
    evidence_summary: str,
    grounded_references: list[str],
    questionnaire_response: dict[str, Any],
    headers: dict[str, str] | None = None,
    mcp_ctx: Context | None = None,
) -> PaEvidencePacket:
    """Draft a Da Vinci PAS-shaped evidence packet for a ServiceRequest.

    Not full PAS IG conformance. The packet is suitable for human review and
    submission via the production PAS endpoint of the responsible payer.
    """
    ctx = _ctx_from_request_headers(headers, ctx=mcp_ctx)
    sr = await fetch_service_request(ctx, service_request_id)
    coverage = await fetch_coverage(ctx)

    service_description = (sr.get("code") or {}).get("text") or "service request"
    narrative = await draft_medical_necessity(
        ctx,
        service_description=service_description,
        evidence_summary=evidence_summary,
        grounded_references=grounded_references,
    )
    bundle = assemble_pas_shaped_bundle(
        service_request=sr,
        coverage=coverage,
        questionnaire_response=questionnaire_response,
        narrative=narrative,
        cited_references=grounded_references,
    )
    risk_level, missing = await predict_denial_risk(
        narrative=narrative,
        cited_references=grounded_references,
        service_description=service_description,
    )

    packet = PaEvidencePacket(
        service_request_ref=f"ServiceRequest/{service_request_id}",
        coverage_ref=f"Coverage/{coverage['id']}" if coverage else None,
        questionnaire_response=questionnaire_response,
        medical_necessity_narrative=narrative,
        pas_bundle=bundle,
        cited_references=grounded_references,
        denial_risk=risk_level,
        missing_items=missing,
    )
    write_entry(
        ctx=ctx,
        actor="mcp:pa_draft_evidence_packet",
        action="pa_packet",
        model_id=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        input_summary=f"service={service_description}",
        output_summary=f"denial_risk={risk_level}",
        cited_resources=grounded_references,
    )
    return packet


@mcp.tool
def healthcheck(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Return server health and version info.

    Accepts (and ignores) `headers` so every tool in this server has a uniform
    signature: agents can always pass SHARP headers without branching.
    """
    del headers  # uniform contract; not needed here
    return {
        "service": "maternasquad-mcp",
        "version": "0.1.0",
        "model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        "fhir_url": os.environ.get("FHIR_BASE_URL", "unset"),
        "now": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    host = os.environ.get("MCP_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_SERVER_PORT", "8080"))
    log.info("server.start", host=host, port=port)
    mcp.run(transport="streamable-http", host=host, port=port)
