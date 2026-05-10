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


app = build_app(agent_name="risk_agent", invoke_handler=_invoke_handler)


if __name__ == "__main__":
    port = int(os.environ.get("RISK_AGENT_PORT", "8002"))
    log.info("risk_agent.start", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104
