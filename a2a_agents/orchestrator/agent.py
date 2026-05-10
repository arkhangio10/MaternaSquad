"""Orchestrator Agent: front door, routes to the squad."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx
import structlog
import uvicorn
from dotenv import load_dotenv

from a2a_agents._base import (
    AgentInvokeRequest,
    build_app,
    load_prompt,
)
from a2a_agents.orchestrator.routing import plan_for
from mcp_server.src.gemini import generate_text
from mcp_server.src.sharp.context import SharpContext

load_dotenv()
log = structlog.get_logger("orchestrator")

AGENT_DIR = Path(__file__).parent
SYSTEM_PROMPT = load_prompt(AGENT_DIR)

SUB_AGENT_URLS = {
    "risk_agent": os.environ.get(
        "RISK_AGENT_URL",
        f"http://localhost:{os.environ.get('RISK_AGENT_PORT', '8002')}/invoke",
    ),
    "coverage_agent": os.environ.get(
        "COVERAGE_AGENT_URL",
        f"http://localhost:{os.environ.get('COVERAGE_AGENT_PORT', '8003')}/invoke",
    ),
    "education_agent": os.environ.get(
        "EDUCATION_AGENT_URL",
        f"http://localhost:{os.environ.get('EDUCATION_AGENT_PORT', '8004')}/invoke",
    ),
    "postpartum_watch_agent": os.environ.get(
        "POSTPARTUM_WATCH_URL",
        f"http://localhost:{os.environ.get('POSTPARTUM_WATCH_PORT', '8005')}/invoke",
    ),
}


async def _call_one(
    client: httpx.AsyncClient,
    agent_name: str,
    url: str,
    request: AgentInvokeRequest,
    sharp_headers: dict[str, str],
) -> tuple[str, dict[str, Any], list[str]]:
    """Invoke one sub-agent. Returns (agent_name, output_dict, cited_refs)."""
    try:
        r = await client.post(
            url,
            json={"user_message": request.user_message, "context": request.context},
            headers=sharp_headers,
        )
        if r.status_code < 400:
            body = r.json()
            return agent_name, body.get("output", {}), body.get("cited_references", []) or []
        return agent_name, {"error": r.text[:200]}, []
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return agent_name, {"error": f"transport: {e!r}"}, []


async def _invoke_handler(
    request: AgentInvokeRequest, ctx: SharpContext, sharp_headers: dict[str, str]
) -> dict[str, Any]:
    plan = plan_for(request.user_message)
    sub_results: dict[str, Any] = {}
    cited: list[str] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        tasks = [
            _call_one(client, agent_name, SUB_AGENT_URLS[agent_name], request, sharp_headers)
            for agent_name in plan
            if agent_name in SUB_AGENT_URLS
        ]
        results = await asyncio.gather(*tasks)

    for agent_name, output, refs in results:
        sub_results[agent_name] = output
        cited += refs

    if cited:
        ref_lines = "\n".join(f"  [{r}]" for r in cited)
        cite_block = (
            "Available FHIR resources (you MUST cite at least one inline as "
            "[ResourceType/id] for every clinical claim):\n" + ref_lines
        )
    else:
        cite_block = "No FHIR resources were returned by sub-agents."

    summary_prompt = f"""User asked: {request.user_message}

Sub-agent results (JSON):
{sub_results}

{cite_block}

Produce a 4 to 6 sentence clinician handoff. For every clinical claim, cite the
resource inline using the exact [ResourceType/id] format shown above. Match the
user's language."""
    try:
        summary = await generate_text(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=summary_prompt,
            require_citations=bool(cited),
            temperature=0.2,
            max_output_tokens=1500,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("orchestrator.summary_failed", error=str(e))
        summary = "Sub-agent results returned. See structured output below."

    return {
        "plan": plan,
        "subagent_outputs": sub_results,
        "clinician_summary": summary,
        "cited_references": list(set(cited)),
    }


app = build_app(agent_name="orchestrator", invoke_handler=_invoke_handler)


if __name__ == "__main__":
    port = int(os.environ.get("ORCHESTRATOR_PORT", "8001"))
    log.info("orchestrator.start", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104
