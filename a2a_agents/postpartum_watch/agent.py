"""Postpartum Watch Agent: 12-week danger window symptom triage."""
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
log = structlog.get_logger("postpartum_watch")

AGENT_DIR = Path(__file__).parent
SYSTEM_PROMPT = load_prompt(AGENT_DIR)


async def _invoke_handler(
    request: AgentInvokeRequest, ctx: SharpContext, sharp_headers: dict[str, str]
) -> dict[str, Any]:
    """Triage a postpartum symptom message and draft an SBAR escalation."""
    pregnancy = await call_mcp_tool(
        tool_name="fhir_get_pregnancy_context", arguments={}, sharp_headers=sharp_headers
    )
    grounded_refs = pregnancy.get("cited_references", [])

    summary = (
        f"Patient {ctx.patient_id}, "
        f"{len(pregnancy.get('conditions', []))} conditions, "
        f"{len(pregnancy.get('observations', []))} recent observations."
    )
    triage = await call_mcp_tool(
        tool_name="postpartum_triage",
        arguments={
            "patient_message": request.user_message,
            "pregnancy_context_summary": summary,
            "grounded_references": grounded_refs,
        },
        sharp_headers=sharp_headers,
    )
    handoff_packet = {
        "communication_resource_skeleton": {
            "resourceType": "Communication",
            "status": "preparation",
            "subject": {"reference": f"Patient/{ctx.patient_id}"},
            "topic": {"text": "Postpartum symptom triage handoff"},
            "payload": [{"contentString": triage.get("clinician_message_draft", "")}],
        },
        "to_role": _route_role(triage.get("urgency", "routine")),
    }
    return {
        "triage": triage,
        "handoff_packet": handoff_packet,
        "cited_references": triage.get("cited_references", []),
    }


def _route_role(urgency: str) -> str:
    if urgency == "911":
        return "911-dispatch"
    if urgency == "urgent_clinic_now":
        return "on-call-OB"
    if urgency == "same_day":
        return "nurse-care-coordinator"
    return "routine-callback-pool"


app = build_app(agent_name="postpartum_watch_agent", invoke_handler=_invoke_handler)


if __name__ == "__main__":
    port = int(os.environ.get("POSTPARTUM_WATCH_PORT", "8005"))
    log.info("postpartum_watch.start", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104
