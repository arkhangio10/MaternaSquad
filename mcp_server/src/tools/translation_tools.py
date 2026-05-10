"""Patient communication tools: translation and reading-level adaptation.

Used by the Education Agent to produce patient-facing teach-back content in
the patient's preferred language and at a controlled reading level.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from mcp_server.src.gemini import generate_text
from mcp_server.src.prompts import load as load_prompt
from mcp_server.src.sharp.context import SharpContext


class PatientMessage(BaseModel):
    locale: str
    reading_level_grade: int = Field(..., ge=3, le=12)
    text: str
    cited_references: list[str] = Field(default_factory=list)


SYSTEM_PROMPT_PATIENT_MSG = load_prompt("patient_message")


async def translate_for_patient(
    ctx: SharpContext,
    *,
    clinical_summary: str,
    grounded_references: list[str],
    target_grade_level: int = 5,
) -> PatientMessage:
    """Translate a clinical summary into patient-facing text in ctx.locale."""
    user_prompt = f"""Target locale: {ctx.locale}
Target reading-level grade: {target_grade_level}

Clinical summary to translate (with FHIR refs):
{clinical_summary}

Grounded FHIR references available:
{chr(10).join(f'- {r}' for r in grounded_references)}

Produce the patient-facing message in {ctx.locale} at grade {target_grade_level}."""

    text = await generate_text(
        system_prompt=SYSTEM_PROMPT_PATIENT_MSG,
        user_prompt=user_prompt,
        require_citations=True,
        temperature=0.3,
        max_output_tokens=800,
    )

    return PatientMessage(
        locale=ctx.locale,
        reading_level_grade=target_grade_level,
        text=text,
        cited_references=grounded_references,
    )


async def warning_signs_card(
    ctx: SharpContext,
    *,
    condition_focus: str,
    grounded_references: list[str],
    target_grade_level: int = 5,
) -> PatientMessage:
    """Produce a 'when to seek care' warning-signs card for a specific condition."""
    user_prompt = f"""Produce a warning-signs card in {ctx.locale} at grade {target_grade_level}.
Condition focus: {condition_focus}

Format:
- Title (1 line)
- 'Call now if you have any of these:' followed by 5 to 7 bullet points
- 'What to do:' with one clear action

Grounded FHIR references:
{chr(10).join(f'- {r}' for r in grounded_references)}"""

    text = await generate_text(
        system_prompt=SYSTEM_PROMPT_PATIENT_MSG,
        user_prompt=user_prompt,
        require_citations=True,
        temperature=0.2,
        max_output_tokens=600,
    )

    return PatientMessage(
        locale=ctx.locale,
        reading_level_grade=target_grade_level,
        text=text,
        cited_references=grounded_references,
    )
