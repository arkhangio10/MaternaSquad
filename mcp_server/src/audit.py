"""Audit trail writer for MaternaSquad.

Writes one JSON line per agent or tool invocation. Production would target
BigQuery or GCS; for the hackathon we use a local file. Never logs PHI: only
resource IDs, types, and SHARP trace context.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import structlog

from mcp_server.src.sharp.context import AuditEntry, SharpContext

log = structlog.get_logger(__name__)


def _audit_path() -> Path:
    p = Path(os.environ.get("AUDIT_LOG_PATH", "./audit/maternasquad.log"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_entry(
    *,
    ctx: SharpContext,
    actor: str,
    action: str,
    model_id: str | None = None,
    input_summary: str = "",
    output_summary: str = "",
    cited_resources: list[str] | None = None,
) -> None:
    """Append one audit entry to the trail."""
    entry = AuditEntry(
        trace_id=ctx.trace_id,
        actor=actor,
        action=action,
        patient_id=ctx.patient_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        model_id=model_id,
        input_summary=input_summary,
        output_summary=output_summary,
        cited_resources=cited_resources or [],
    )
    line = json.dumps(entry.model_dump(), separators=(",", ":"))
    with _audit_path().open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    log.info("audit.write", actor=actor, action=action, trace_id=ctx.trace_id)
