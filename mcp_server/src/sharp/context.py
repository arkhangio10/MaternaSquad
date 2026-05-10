"""SHARP Extension Specs context for healthcare agent calls.

SHARP is Prompt Opinion's spec for propagating healthcare context across MCP
tool calls and A2A agent hops. The official spec from Prompt Opinion takes
precedence. Until confirmed, we use the header conventions below.

Reference: https://promptopinion.ai (check resources page for canonical spec)
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

# Header name constants. If the official SHARP spec uses different names,
# change them here in one place.
HEADER_PATIENT_ID = "X-SHARP-Patient-Id"
HEADER_FHIR_SERVER_URL = "X-SHARP-FHIR-Server-URL"
HEADER_FHIR_ACCESS_TOKEN = "X-SHARP-FHIR-Access-Token"
HEADER_ENCOUNTER_ID = "X-SHARP-Encounter-Id"
HEADER_USER_ROLE = "X-SHARP-User-Role"
HEADER_TRACE_ID = "X-SHARP-Trace-Id"
HEADER_LOCALE = "X-SHARP-Locale"

UserRole = Literal["clinician", "patient", "care-coordinator", "system"]


class SharpContext(BaseModel):
    """The healthcare context that flows across every agent and tool call.

    Each MCP tool and A2A agent receives this and must propagate it on any
    outbound call to another tool or agent. This is how SHARP keeps the
    patient identity and FHIR session consistent across multi-agent workflows.
    """

    patient_id: str = Field(..., description="FHIR Patient resource ID for the active patient")
    fhir_server_url: str = Field(..., description="Base URL of the FHIR R4 server")
    fhir_access_token: str | None = Field(
        default=None, description="Bearer token for FHIR access. None for open dev servers."
    )
    encounter_id: str | None = Field(default=None, description="Current Encounter ID, if any")
    user_role: UserRole = Field(default="clinician", description="Role of the human user")
    trace_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID propagated end-to-end for audit",
    )
    locale: str = Field(
        default="en-US", description="BCP-47 language tag for patient-facing communication"
    )

    def to_headers(self) -> dict[str, str]:
        """Serialize this context to outbound HTTP headers."""
        headers = {
            HEADER_PATIENT_ID: self.patient_id,
            HEADER_FHIR_SERVER_URL: self.fhir_server_url,
            HEADER_USER_ROLE: self.user_role,
            HEADER_TRACE_ID: self.trace_id,
            HEADER_LOCALE: self.locale,
        }
        if self.fhir_access_token:
            headers[HEADER_FHIR_ACCESS_TOKEN] = self.fhir_access_token
        if self.encounter_id:
            headers[HEADER_ENCOUNTER_ID] = self.encounter_id
        return headers

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> SharpContext:
        """Parse SHARP context from inbound HTTP headers.

        Header lookup is case-insensitive. Accepts the Prompt Opinion FHIR
        context headers (`X-FHIR-Server-URL`, `X-FHIR-Access-Token`,
        `X-Patient-ID`) as fallbacks for the SHARP variants, so the same MCP
        works whether called by our own A2A agents (SHARP headers) or by Po
        (FHIR-context headers).
        """
        norm = {k.lower(): v for k, v in headers.items()}

        def get(*names: str) -> str | None:
            for n in names:
                v = norm.get(n.lower())
                if v:
                    return v
            return None

        patient_id = get(HEADER_PATIENT_ID, "x-patient-id")
        fhir_server_url = get(HEADER_FHIR_SERVER_URL, "x-fhir-server-url")
        if not patient_id or not fhir_server_url:
            raise ValueError(
                "Missing FHIR context: need either SHARP headers "
                f"({HEADER_PATIENT_ID} + {HEADER_FHIR_SERVER_URL}) "
                "or Prompt Opinion headers (x-patient-id + x-fhir-server-url)."
            )

        access_token = get(HEADER_FHIR_ACCESS_TOKEN, "x-fhir-access-token")
        if access_token and access_token.lower().startswith("bearer "):
            access_token = access_token[7:].strip()

        return cls(
            patient_id=patient_id,
            fhir_server_url=fhir_server_url,
            fhir_access_token=access_token,
            encounter_id=get(HEADER_ENCOUNTER_ID),
            user_role=get(HEADER_USER_ROLE) or "clinician",  # type: ignore[arg-type]
            trace_id=get(HEADER_TRACE_ID) or str(uuid.uuid4()),
            locale=get(HEADER_LOCALE) or "en-US",
        )


class AuditEntry(BaseModel):
    """One row of the audit trail. Logged for every tool and agent call."""

    trace_id: str
    actor: str = Field(..., description="Tool or agent name that produced this entry")
    action: str = Field(..., description="What was done, e.g. 'fhir_get_pregnancy_context'")
    patient_id: str
    timestamp: str
    model_id: str | None = Field(default=None, description="LLM model version if applicable")
    input_summary: str = Field(default="", description="Short non-PHI input description")
    output_summary: str = Field(default="", description="Short non-PHI output description")
    cited_resources: list[str] = Field(
        default_factory=list, description="FHIR resource references this output is grounded in"
    )
