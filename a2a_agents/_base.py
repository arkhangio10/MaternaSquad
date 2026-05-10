"""Shared base for MaternaSquad A2A agents.

Each specialist agent loads its system prompt from its own prompts/system.md,
configures a Gemini-backed agent, and exposes an HTTP endpoint that consumes
SHARP context headers and forwards them to the MCP server.

This file is a thin wrapper. It avoids tight coupling to any single A2A SDK so
we can swap Google ADK for another implementation later.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from mcp_server.src.audit import write_entry
from mcp_server.src.sharp.context import SharpContext

log = structlog.get_logger(__name__)


def load_prompt(agent_dir: Path) -> str:
    """Load `prompts/system.md` for an agent. Strips YAML frontmatter."""
    path = agent_dir / "prompts" / "system.md"
    text = path.read_text(encoding="utf-8")
    # Strip YAML frontmatter if present
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :].lstrip()
    return text


class AgentInvokeRequest(BaseModel):
    """Inbound request to an A2A agent endpoint."""

    user_message: str
    context: dict[str, Any] = {}


class AgentInvokeResponse(BaseModel):
    """Outbound A2A response."""

    agent: str
    output: dict[str, Any]
    cited_references: list[str] = []
    trace_id: str


def headers_dict(
    sharp_patient_id: str | None,
    sharp_fhir_url: str | None,
    sharp_token: str | None,
    sharp_encounter: str | None,
    sharp_role: str | None,
    sharp_trace: str | None,
    sharp_locale: str | None,
) -> dict[str, str]:
    """Reassemble SHARP headers from FastAPI Header() params."""
    out: dict[str, str] = {}
    if sharp_patient_id:
        out["X-SHARP-Patient-Id"] = sharp_patient_id
    if sharp_fhir_url:
        out["X-SHARP-FHIR-Server-URL"] = sharp_fhir_url
    if sharp_token:
        out["X-SHARP-FHIR-Access-Token"] = sharp_token
    if sharp_encounter:
        out["X-SHARP-Encounter-Id"] = sharp_encounter
    if sharp_role:
        out["X-SHARP-User-Role"] = sharp_role
    if sharp_trace:
        out["X-SHARP-Trace-Id"] = sharp_trace
    if sharp_locale:
        out["X-SHARP-Locale"] = sharp_locale
    return out


async def call_mcp_tool(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    sharp_headers: dict[str, str],
) -> dict[str, Any]:
    """Invoke an MCP tool through the FastMCP streamable-http transport.

    SHARP context flows two ways: as HTTP-level headers on the transport
    (so any SHARP-aware middleware sees them) and as a `headers` field in
    the tool arguments (since tool signatures in `server.py` accept
    `headers: dict[str, str] | None = None`).
    """
    from fastmcp import Client  # imported lazily to keep startup fast
    from fastmcp.client.transports import StreamableHttpTransport

    base_url = os.environ.get("MCP_BASE_URL", "http://localhost:8080")
    mcp_url = f"{base_url.rstrip('/')}/mcp"
    payload = dict(arguments)
    payload.setdefault("headers", sharp_headers)

    transport = StreamableHttpTransport(url=mcp_url, headers=sharp_headers)
    log.info("mcp.call", tool=tool_name, trace_id=sharp_headers.get("X-SHARP-Trace-Id"))
    async with Client(transport) as client:
        result = await client.call_tool(tool_name, payload)

    # FastMCP returns a CallToolResult. For tools that return Pydantic models,
    # structured_content is a plain dict; result.data is a FastMCP-internal
    # Root object that is NOT a dict. Always prefer structured_content when
    # available, fall back to data, then text content blocks.
    data: Any = getattr(result, "structured_content", None)
    if data is None:
        data = getattr(result, "data", None)
    if data is None:
        # Last resort: join text content blocks.
        blocks = getattr(result, "content", None) or []
        text = "".join(getattr(b, "text", "") for b in blocks)
        data = {"text": text} if text else {}
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    if not isinstance(data, dict):
        data = {"value": data}
    return data


def build_app(
    *,
    agent_name: str,
    invoke_handler: Any,
    agent_card: dict[str, Any] | None = None,
) -> FastAPI:
    """Build a FastAPI app exposing the standard A2A invoke endpoint.

    `agent_card` is the A2A protocol agent metadata. The `url` field is
    filled at request time from the public base URL the request arrived on,
    so the same code works locally on http://localhost:8001 and on Cloud Run.
    """
    app = FastAPI(title=agent_name, version="0.1.0")

    @app.get("/healthcheck")
    def healthcheck() -> dict[str, str]:
        return {"agent": agent_name, "status": "ok"}

    @app.get("/.well-known/agent-card.json")
    def get_agent_card(request: Request) -> dict[str, Any]:
        # Cloud Run terminates TLS upstream so request.url.scheme is "http";
        # honor X-Forwarded-Proto so the published URL is the real https one.
        base = str(request.base_url).rstrip("/")
        if request.headers.get("x-forwarded-proto") == "https" and base.startswith(
            "http://"
        ):
            base = "https://" + base[len("http://") :]

        card = agent_card or {}
        caps = card.get("capabilities", {})
        return {
            "protocolVersion": card.get("protocol_version", "0.2.0"),
            "name": card.get("name", f"MaternaSquad {agent_name}"),
            "description": card.get("description", f"MaternaSquad {agent_name}"),
            "url": base,
            "version": card.get("version", "0.1.0"),
            "provider": card.get(
                "provider",
                {
                    "organization": "MaternaSquad",
                    "url": "https://github.com/arkhangio10/MaternaSquad",
                },
            ),
            "capabilities": {
                "streaming": caps.get("streaming", False),
                "pushNotifications": caps.get("push_notifications", False),
            },
            "defaultInputModes": card.get(
                "default_input_modes", ["text/plain", "application/json"]
            ),
            "defaultOutputModes": card.get(
                "default_output_modes", ["application/json"]
            ),
            "skills": card.get("skills", []),
            "supportedInterfaces": [
                {"transport": "HTTP+JSON", "url": f"{base}/invoke"},
            ],
        }

    @app.post("/invoke", response_model=AgentInvokeResponse)
    async def invoke(
        request: AgentInvokeRequest,
        x_sharp_patient_id: str | None = Header(default=None, alias="X-SHARP-Patient-Id"),
        x_sharp_fhir_server_url: str | None = Header(default=None, alias="X-SHARP-FHIR-Server-URL"),
        x_sharp_fhir_access_token: str | None = Header(
            default=None, alias="X-SHARP-FHIR-Access-Token"
        ),
        x_sharp_encounter_id: str | None = Header(default=None, alias="X-SHARP-Encounter-Id"),
        x_sharp_user_role: str | None = Header(default=None, alias="X-SHARP-User-Role"),
        x_sharp_trace_id: str | None = Header(default=None, alias="X-SHARP-Trace-Id"),
        x_sharp_locale: str | None = Header(default=None, alias="X-SHARP-Locale"),
    ) -> AgentInvokeResponse:
        sharp_headers = headers_dict(
            x_sharp_patient_id,
            x_sharp_fhir_server_url,
            x_sharp_fhir_access_token,
            x_sharp_encounter_id,
            x_sharp_user_role,
            x_sharp_trace_id,
            x_sharp_locale,
        )
        ctx = SharpContext.from_headers(sharp_headers) if sharp_headers else None
        if not ctx:
            raise HTTPException(status_code=400, detail="Missing SHARP context headers")

        result = await invoke_handler(request, ctx, sharp_headers)
        cited: list[str] = result.get("cited_references", []) if isinstance(result, dict) else []
        write_entry(
            ctx=ctx,
            actor=f"agent:{agent_name}",
            action="invoke",
            input_summary=request.user_message[:120],
            output_summary=str(result)[:200],
            cited_resources=cited,
        )
        return AgentInvokeResponse(
            agent=agent_name, output=result, cited_references=cited, trace_id=ctx.trace_id
        )

    return app
