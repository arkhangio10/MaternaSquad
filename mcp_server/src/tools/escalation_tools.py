"""Symptom triage and escalation routing for the Postpartum Watch Agent.

Classifies a patient-reported symptom into urgency tier and produces a
structured escalation packet (clinician message draft, suggested action, FHIR
Communication resource skeleton).

This is decision support, not autonomous decision making. Every output points
back to the published warning-signs guideline (CDC Hear Her, ACOG PB 736).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from mcp_server.src.gemini import generate_structured
from mcp_server.src.prompts import load as load_prompt
from mcp_server.src.sharp.context import SharpContext

UrgencyTier = Literal["911", "urgent_clinic_now", "same_day", "routine"]


class TriageDecision(BaseModel):
    urgency: UrgencyTier
    symptom_summary: str
    matched_warning_signs: list[str] = Field(
        default_factory=list,
        description="CDC Hear Her warning signs that match the report",
    )
    suggested_action: str
    clinician_message_draft: str
    cited_references: list[str] = Field(default_factory=list)
    guideline_source: str = "CDC Hear Her; ACOG Practice Bulletin No. 736 (Postpartum Care)"


SYSTEM_PROMPT_TRIAGE = load_prompt("triage")


async def triage_symptom(
    ctx: SharpContext,
    *,
    patient_message: str,
    pregnancy_context_summary: str,
    grounded_references: list[str],
) -> TriageDecision:
    """Classify a patient symptom message and draft an escalation packet."""
    user_prompt = f"""Patient is in postpartum period (within 12 weeks of delivery).
Patient message (verbatim): {patient_message!r}

Pregnancy context summary:
{pregnancy_context_summary}

Grounded FHIR references available:
{chr(10).join(f'- {r}' for r in grounded_references)}

Classify urgency, list matched CDC Hear Her warning signs, draft a clinician
message in SBAR format, and suggest the next action."""

    decision = await generate_structured(
        system_prompt=SYSTEM_PROMPT_TRIAGE,
        user_prompt=user_prompt,
        schema=TriageDecision,
        temperature=0.0,
        max_output_tokens=1500,
    )
    if not decision.cited_references:
        decision.cited_references = grounded_references
    return decision
