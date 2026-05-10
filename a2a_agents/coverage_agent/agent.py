"""Coverage Agent: drafts Da Vinci PAS-shaped evidence packets."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
import uvicorn
from dotenv import load_dotenv

from a2a_agents._base import AgentInvokeRequest, build_app, call_mcp_tool, load_prompt
from mcp_server.src.sharp.context import SharpContext

load_dotenv()
log = structlog.get_logger("coverage_agent")

AGENT_DIR = Path(__file__).parent
SYSTEM_PROMPT = load_prompt(AGENT_DIR)


async def _invoke_handler(
    request: AgentInvokeRequest, ctx: SharpContext, sharp_headers: dict[str, str]
) -> dict[str, Any]:
    """Build a PA evidence packet for the requested service.

    Expects request.context to carry a `service_request_id` and an
    `evidence_summary`. Returns the packet plus a clinician summary.
    """
    service_request_id = request.context.get("service_request_id")
    if not service_request_id:
        return {"error": "service_request_id required in context"}

    pregnancy = await call_mcp_tool(
        tool_name="fhir_get_pregnancy_context", arguments={}, sharp_headers=sharp_headers
    )
    grounded_refs = pregnancy.get("cited_references", [])
    evidence_summary = request.context.get("evidence_summary") or _summarize(pregnancy)

    questionnaire_response = request.context.get("questionnaire_response", {
        "resourceType": "QuestionnaireResponse",
        "status": "completed",
        "item": [],
    })

    packet = await call_mcp_tool(
        tool_name="pa_draft_evidence_packet",
        arguments={
            "service_request_id": service_request_id,
            "evidence_summary": evidence_summary,
            "grounded_references": grounded_refs,
            "questionnaire_response": questionnaire_response,
        },
        sharp_headers=sharp_headers,
    )
    return packet


def _summarize(pregnancy: dict[str, Any]) -> str:
    summary_parts = [
        f"Patient {pregnancy.get('patient_id')}",
        f"{len(pregnancy.get('conditions', []))} conditions",
        f"{len(pregnancy.get('observations', []))} observations",
        f"{len(pregnancy.get('medications', []))} medications",
    ]
    return "; ".join(summary_parts)


app = build_app(agent_name="coverage_agent", invoke_handler=_invoke_handler)


if __name__ == "__main__":
    port = int(os.environ.get("COVERAGE_AGENT_PORT", "8003"))
    log.info("coverage_agent.start", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104
