"""Education Agent: patient-facing teach-back content."""
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
log = structlog.get_logger("education_agent")

AGENT_DIR = Path(__file__).parent
SYSTEM_PROMPT = load_prompt(AGENT_DIR)


async def _invoke_handler(
    request: AgentInvokeRequest, ctx: SharpContext, sharp_headers: dict[str, str]
) -> dict[str, Any]:
    """Produce a patient-facing card for the requested topic.

    Expects request.context.topic and an optional grade_level. Pulls grounded
    refs from MCP fhir_get_pregnancy_context if not supplied.
    """
    topic = request.context.get("topic", "general pregnancy guidance")
    grade_level = int(request.context.get("grade_level", 5))
    grounded_refs = request.context.get("grounded_references")

    if not grounded_refs:
        pregnancy = await call_mcp_tool(
            tool_name="fhir_get_pregnancy_context", arguments={}, sharp_headers=sharp_headers
        )
        grounded_refs = pregnancy.get("cited_references", [])

    if "warning" in topic.lower():
        result = await call_mcp_tool(
            tool_name="patient_warning_signs_card",
            arguments={
                "condition_focus": topic,
                "grounded_references": grounded_refs,
                "target_grade_level": grade_level,
            },
            sharp_headers=sharp_headers,
        )
    else:
        result = await call_mcp_tool(
            tool_name="patient_translate_message",
            arguments={
                "clinical_summary": topic,
                "grounded_references": grounded_refs,
                "target_grade_level": grade_level,
            },
            sharp_headers=sharp_headers,
        )
    return {
        "patient_message": result,
        "cited_references": grounded_refs,
    }


AGENT_CARD = {
    "protocol_version": "0.2.0",
    "name": "MaternaSquad Education Agent",
    "description": (
        "Generates patient-facing education and warning-signs material at "
        "grade-5 reading level in the patient's locale (en-US, es-US confirmed). "
        "Always cites FHIR Conditions / Observations / MedicationRequests and "
        "returns the English back-translation for clinician review."
    ),
    "version": "0.1.0",
    "provider": {"organization": "MaternaSquad", "url": "https://github.com/arkhangio10/MaternaSquad"},
    "capabilities": {"streaming": False, "push_notifications": False},
    "default_input_modes": ["text/plain", "application/json"],
    "default_output_modes": ["application/json"],
    "skills": [
        {
            "id": "patient_translate_message",
            "name": "Patient education message",
            "description": "Produce a plain-language patient message about the patient's care plan, with FHIR citations.",
            "tags": ["patient-education", "multilingual", "grade-5"],
            "examples": [
                "Generate the patient education message about her current pregnancy plan."
            ],
        },
        {
            "id": "warning_signs_card",
            "name": "Warning-signs card",
            "description": "Localized warning-signs card the patient can keep on a phone or print.",
            "tags": ["patient-education", "warning-signs", "CDC-Hear-Her"],
            "examples": [
                "Create the postpartum warning signs card. Locale es-US."
            ],
        },
    ],
}

app = build_app(
    agent_name="education_agent",
    invoke_handler=_invoke_handler,
    agent_card=AGENT_CARD,
)


if __name__ == "__main__":
    port = int(os.environ.get("EDUCATION_AGENT_PORT", "8004"))
    log.info("education_agent.start", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104
