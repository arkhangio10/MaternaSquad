"""Coverage and prior authorization helper tools.

Lightweight helpers for the Coverage Agent. Builds Da Vinci PAS-shaped Bundles
from a ServiceRequest plus collected evidence. Not full IG conformance; framed
as 'PA evidence packet ready for human review and submission'.

Reference: HL7 Da Vinci PAS IG v2.1.0 https://hl7.org/fhir/us/davinci-pas/
"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from mcp_server.src.fhir.client import FhirClient
from mcp_server.src.gemini import generate_text
from mcp_server.src.prompts import load as load_prompt
from mcp_server.src.sharp.context import SharpContext


class PaEvidencePacket(BaseModel):
    service_request_ref: str
    coverage_ref: str | None = None
    questionnaire_response: dict[str, Any] = Field(default_factory=dict)
    medical_necessity_narrative: str
    pas_bundle: dict[str, Any] = Field(default_factory=dict)
    cited_references: list[str] = Field(default_factory=list)
    denial_risk: str = "unknown"  # 'low' | 'medium' | 'high' | 'unknown'
    missing_items: list[str] = Field(default_factory=list)


SYSTEM_PROMPT_PA_NARRATIVE = load_prompt("pa_narrative")


async def draft_medical_necessity(
    ctx: SharpContext,
    *,
    service_description: str,
    evidence_summary: str,
    grounded_references: list[str],
) -> str:
    """Generate a 4-6 sentence medical-necessity paragraph with citations."""
    user_prompt = f"""Service or item being requested: {service_description}

Evidence summary (with FHIR refs):
{evidence_summary}

Available grounded references:
{chr(10).join(f'- {r}' for r in grounded_references)}

Write the medical-necessity narrative."""
    return await generate_text(
        system_prompt=SYSTEM_PROMPT_PA_NARRATIVE,
        user_prompt=user_prompt,
        require_citations=True,
        temperature=0.2,
        max_output_tokens=500,
    )


def assemble_pas_shaped_bundle(
    *,
    service_request: dict[str, Any],
    coverage: dict[str, Any] | None,
    questionnaire_response: dict[str, Any],
    narrative: str,
    cited_references: list[str],
) -> dict[str, Any]:
    """Assemble a PAS-shaped FHIR Bundle (not full IG conformance).

    Suitable for hackathon demo. Production deployment must validate against
    the Da Vinci PAS IG profiles.
    """
    bundle_id = str(uuid.uuid4())
    entries: list[dict[str, Any]] = [
        {"resource": service_request, "fullUrl": f"urn:uuid:{service_request['id']}"},
        {"resource": questionnaire_response, "fullUrl": f"urn:uuid:{uuid.uuid4()}"},
    ]
    if coverage:
        entries.append({"resource": coverage, "fullUrl": f"urn:uuid:{coverage['id']}"})

    composition = {
        "resourceType": "Composition",
        "id": str(uuid.uuid4()),
        "status": "preliminary",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "57133-1",
                    "display": "Referral note",
                }
            ]
        },
        "title": "Prior authorization evidence packet",
        "section": [
            {
                "title": "Medical necessity",
                "text": {"status": "additional", "div": f"<div>{narrative}</div>"},
            },
            {
                "title": "Cited evidence",
                "entry": [{"reference": r} for r in cited_references],
            },
        ],
    }
    entries.insert(0, {"resource": composition, "fullUrl": f"urn:uuid:{composition['id']}"})

    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "document",
        "entry": entries,
    }


async def predict_denial_risk(
    *,
    narrative: str,
    cited_references: list[str],
    service_description: str,
) -> tuple[str, list[str]]:
    """Heuristic denial-risk prediction. Returns (level, missing_items)."""
    if len(cited_references) < 3:
        return "high", ["Additional clinical evidence (need 3+ FHIR resources cited)."]
    if "guideline" not in narrative.lower() and "acog" not in narrative.lower():
        return "medium", ["Cite a clinical guideline (e.g. ACOG, USPSTF) by name and year."]
    return "low", []


async def fetch_service_request(ctx: SharpContext, service_request_id: str) -> dict[str, Any]:
    async with FhirClient(ctx) as fhir:
        return await fhir.read("ServiceRequest", service_request_id)


async def fetch_coverage(ctx: SharpContext) -> dict[str, Any] | None:
    async with FhirClient(ctx) as fhir:
        results = await fhir.search(
            "Coverage", {"patient": ctx.patient_id, "status": "active"}, count=1
        )
        return results[0] if results else None
