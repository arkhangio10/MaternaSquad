"""Pure-Python keyword routing for the Orchestrator.

Lives in its own module so unit tests can import the routing logic without
pulling in `google-genai` or any other heavy LLM dependency. Replace this
with a Gemini tool-calling planning loop post-hackathon.
"""
from __future__ import annotations


def plan_for(user_message: str) -> list[str]:
    """Choose which sub-agents to invoke based on keyword matching.

    Args:
        user_message: The clinician or patient utterance.

    Returns:
        Ordered list of sub-agent names. Always non-empty: falls back to
        ['risk_agent'] when no keyword matches, since the demo path always
        wants at least a risk read.
    """
    msg = user_message.lower()
    plan: list[str] = []
    if any(k in msg for k in ["risk", "third trimester", "preeclampsia", "gdm", "preterm", "set up"]):
        plan.append("risk_agent")
    if any(k in msg for k in ["prior auth", "pa", "coverage", "monitor", "device", "medication"]):
        plan.append("coverage_agent")
    if any(k in msg for k in ["explain", "teach", "warning sign", "education", "patient"]):
        plan.append("education_agent")
    if any(k in msg for k in ["headache", "vision", "pain", "bleeding", "fever", "postpartum"]):
        plan.append("postpartum_watch_agent")
    if not plan:
        plan = ["risk_agent"]
    return plan
