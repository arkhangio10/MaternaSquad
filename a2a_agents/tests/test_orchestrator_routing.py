"""Pin orchestrator keyword routing.

The orchestrator currently routes by keyword (replacement with Gemini
tool-calling planning is post-hackathon). These tests lock in the demo-path
behavior so future refactors do not silently break the storyboard:

- "Set up Aisha for the third trimester" must hit risk_agent.
- A postpartum symptom message must hit postpartum_watch_agent.
- A prior-auth ask must hit coverage_agent.
- A request to explain something to a patient must hit education_agent.
- An empty/unknown message must still produce a non-empty plan.
"""
from __future__ import annotations

from a2a_agents.orchestrator.routing import plan_for


def test_third_trimester_setup_routes_to_risk() -> None:
    plan = plan_for("Set up Aisha for the third trimester. She has been complaining about headaches.")
    assert "risk_agent" in plan
    # Headache is a CDC Hear Her warning sign so the watch agent should also fire.
    assert "postpartum_watch_agent" in plan


def test_postpartum_headache_message_routes_to_watch() -> None:
    plan = plan_for("Me duele mucho la cabeza, no puedo ver bien.")
    # The Spanish demo line does not match keywords; fallback should still
    # produce a non-empty plan (risk_agent default).
    assert plan, "plan must not be empty"
    plan_en = plan_for("postpartum headache, vision changes")
    assert "postpartum_watch_agent" in plan_en


def test_prior_auth_request_routes_to_coverage() -> None:
    plan = plan_for("I need to authorize a home BP monitor for this patient.")
    assert "coverage_agent" in plan


def test_patient_education_routes_to_education() -> None:
    plan = plan_for("Generate a Spanish warning sign card for the patient.")
    assert "education_agent" in plan


def test_unknown_message_falls_back_to_risk() -> None:
    plan = plan_for("hello")
    assert plan == ["risk_agent"]
