"""Claude (Anthropic) backend replacing the former Gemini/Vertex AI integration.

Public interface is identical to the original gemini.py so every caller works
without modification:
  generate_text()       -- free-text narrative with optional citation enforcement
  generate_structured() -- Pydantic-typed output via Claude tool use
  CITATION_PATTERN      -- FHIR [ResourceType/id] inline citation regex
  cited_references()    -- extract citations from a narrative string

Environment variables:
  ANTHROPIC_API_KEY  -- required
  CLAUDE_MODEL       -- optional, defaults to claude-opus-4-7
"""
from __future__ import annotations

import os
import re
from typing import TypeVar

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# A FHIR reference token in narrative text, e.g. [Observation/abc-123].
CITATION_PATTERN = re.compile(
    r"\[(Patient|Condition|Observation|MedicationRequest|ServiceRequest|"
    r"Encounter|Procedure|AllergyIntolerance|CarePlan|Coverage|Claim|"
    r"DocumentReference|Communication|Practitioner|RiskAssessment)/[A-Za-z0-9\-\.]+\]"
)


class GeminiCitationError(ValueError):
    """Raised when a clinical narrative lacks at least one FHIR citation."""


def _client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _model_id() -> str:
    return os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")


async def generate_text(
    *,
    system_prompt: str,
    user_prompt: str,
    require_citations: bool = True,
    temperature: float = 0.2,  # kept for interface compatibility; Opus 4.7 ignores it
    max_output_tokens: int = 1024,
) -> str:
    """Generate free-text narrative. Enforces FHIR citations when require_citations=True."""
    client = _client()
    model = _model_id()
    log.info("claude.generate_text", model=model)
    response = await client.messages.create(
        model=model,
        max_tokens=max_output_tokens,
        thinking={"type": "adaptive"},
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # Skip thinking blocks; take the first text block as the clinical output.
    text = next(
        (block.text for block in response.content if block.type == "text"),
        "",
    )
    if require_citations and not CITATION_PATTERN.search(text):
        raise GeminiCitationError(
            "Clinical narrative produced without FHIR citations. "
            "The prompt must require [ResourceType/id] tokens. Refusing to return."
        )
    return text


async def generate_structured(
    *,
    system_prompt: str,
    user_prompt: str,
    schema: type[T],
    temperature: float = 0.0,  # kept for interface compatibility; Opus 4.7 ignores it
    max_output_tokens: int = 2048,
) -> T:
    """Generate a Pydantic-typed response via Claude tool use."""
    client = _client()
    model = _model_id()
    log.info("claude.generate_structured", model=model, schema=schema.__name__)

    tool_name = schema.__name__
    tool = {
        "name": tool_name,
        "description": f"Return a structured {tool_name} object with all required fields populated.",
        "input_schema": schema.model_json_schema(),
    }

    response = await client.messages.create(
        model=model,
        max_tokens=max_output_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool_name},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return schema.model_validate(block.input)

    raise ValueError(f"Claude did not return a {tool_name} tool call. Stop reason: {response.stop_reason}")


def cited_references(text: str) -> list[str]:
    """Extract all [ResourceType/id] citations from a narrative."""
    return [m.group(0).strip("[]") for m in CITATION_PATTERN.finditer(text)]
