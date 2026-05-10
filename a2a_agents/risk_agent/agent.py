"""Risk Agent: ACOG/USPSTF-grounded risk stratification."""
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
log = structlog.get_logger("risk_agent")

AGENT_DIR = Path(__file__).parent
SYSTEM_PROMPT = load_prompt(AGENT_DIR)


async def _invoke_handler(
    request: AgentInvokeRequest, ctx: SharpContext, sharp_headers: dict[str, str]
) -> dict[str, Any]:
    """Run all three risk scorers and return a combined report."""
    pe = await call_mcp_tool(
        tool_name="acog_preeclampsia_risk", arguments={}, sharp_headers=sharp_headers
    )
    gdm = await call_mcp_tool(
        tool_name="acog_gdm_risk", arguments={}, sharp_headers=sharp_headers
    )
    ptb = await call_mcp_tool(
        tool_name="acog_preterm_birth_risk", arguments={}, sharp_headers=sharp_headers
    )

    cited = list({*pe.get("cited_references", []), *gdm.get("cited_references", []), *ptb.get("cited_references", [])})

    return {
        "patient_ref": f"Patient/{ctx.patient_id}",
        "risks": [pe, gdm, ptb],
        "cited_references": cited,
    }


AGENT_CARD = {
    "protocol_version": "0.2.0",
    "name": "MaternaSquad Risk Agent",
    "description": (
        "ACOG / USPSTF / ADA grounded risk stratification for preeclampsia, "
        "gestational diabetes, and preterm birth. Deterministic scorers; every "
        "factor cites a FHIR resource, every rule cites the published guideline."
    ),
    "version": "0.1.0",
    "provider": {"organization": "MaternaSquad", "url": "https://github.com/arkhangio10/MaternaSquad"},
    "capabilities": {"streaming": False, "push_notifications": False},
    "default_input_modes": ["text/plain", "application/json"],
    "default_output_modes": ["application/json"],
    "skills": [
        {
            "id": "preeclampsia_risk",
            "name": "Preeclampsia risk",
            "description": "Risk score per USPSTF Aspirin 2021 and ACOG PB 222 (2020) with FHIR-cited factors.",
            "tags": ["preeclampsia", "USPSTF", "ACOG-PB-222"],
            "examples": ["Run preeclampsia risk on this patient."],
        },
        {
            "id": "gdm_risk",
            "name": "Gestational diabetes risk",
            "description": "Screening per ACOG PB 234 (2021) and ADA Standards 2024.",
            "tags": ["GDM", "ACOG-PB-234", "ADA"],
            "examples": ["Screen this patient for gestational diabetes."],
        },
        {
            "id": "preterm_birth_risk",
            "name": "Preterm birth risk",
            "description": "Screening per ACOG PB 232 (2021).",
            "tags": ["preterm-birth", "ACOG-PB-232"],
            "examples": ["Run preterm birth risk on this patient."],
        },
    ],
}

app = build_app(
    agent_name="risk_agent",
    invoke_handler=_invoke_handler,
    agent_card=AGENT_CARD,
)


if __name__ == "__main__":
    port = int(os.environ.get("RISK_AGENT_PORT", "8002"))
    log.info("risk_agent.start", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104
