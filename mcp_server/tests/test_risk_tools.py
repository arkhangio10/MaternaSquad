"""Tests for the deterministic risk scorers.

These run without HAPI or Vertex AI: they pass synthetic PregnancyContext
objects directly into the scorers and assert level + citations.
"""
from __future__ import annotations

from mcp_server.src.tools.fhir_tools import (
    LOINC_A1C,
    LOINC_BMI,
    LOINC_BP_DIASTOLIC,
    LOINC_BP_SYSTOLIC,
    LOINC_URINE_PROTEIN,
    SNOMED_PREECLAMPSIA,
    SNOMED_PRETERM_HISTORY,
    PregnancyContext,
)
from mcp_server.src.tools.risk_tools import (
    gdm_risk,
    preeclampsia_risk,
    preterm_birth_risk,
)


def _obs(loinc: str, value: float, obs_id: str) -> dict:
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "code": {"coding": [{"system": "http://loinc.org", "code": loinc}]},
        "valueQuantity": {"value": value},
    }


def _condition(snomed: str, cond_id: str) -> dict:
    return {
        "resourceType": "Condition",
        "id": cond_id,
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": snomed}]},
    }


def test_preeclampsia_high_when_prior_preeclampsia_present() -> None:
    ctx = PregnancyContext(
        patient_id="aisha",
        conditions=[_condition(SNOMED_PREECLAMPSIA, "cond-1")],
        observations=[
            _obs(LOINC_BP_SYSTOLIC, 142, "obs-bp1"),
            _obs(LOINC_BP_DIASTOLIC, 92, "obs-bp2"),
            _obs(LOINC_BMI, 31.0, "obs-bmi"),
        ],
    )
    score = preeclampsia_risk(ctx)
    assert score.level == "high"
    assert "ACOG" in score.guideline_source or "USPSTF" in score.guideline_source
    assert "Condition/cond-1" in score.cited_references


def test_preeclampsia_low_when_no_factors() -> None:
    ctx = PregnancyContext(
        patient_id="healthy",
        observations=[
            _obs(LOINC_BP_SYSTOLIC, 110, "obs-bp1"),
            _obs(LOINC_BP_DIASTOLIC, 70, "obs-bp2"),
            _obs(LOINC_BMI, 24.0, "obs-bmi"),
        ],
    )
    score = preeclampsia_risk(ctx)
    assert score.level == "low"


def test_gdm_high_when_a1c_elevated() -> None:
    ctx = PregnancyContext(
        patient_id="sofia",
        observations=[
            _obs(LOINC_A1C, 5.9, "obs-a1c"),
            _obs(LOINC_BMI, 28.0, "obs-bmi"),
        ],
    )
    score = gdm_risk(ctx)
    assert score.level == "high"
    assert any("Observation/obs-a1c" in r for r in score.cited_references)


def test_preterm_high_when_history_present() -> None:
    ctx = PregnancyContext(
        patient_id="aisha",
        conditions=[_condition(SNOMED_PRETERM_HISTORY, "cond-pt")],
    )
    score = preterm_birth_risk(ctx)
    assert score.level == "high"
    assert "Condition/cond-pt" in score.cited_references
    assert "ACOG" in score.guideline_source


def test_proteinuria_marks_preeclampsia_high() -> None:
    ctx = PregnancyContext(
        patient_id="aisha",
        observations=[
            _obs(LOINC_URINE_PROTEIN, 0.5, "obs-up"),
            _obs(LOINC_BP_SYSTOLIC, 130, "obs-bp1"),
            _obs(LOINC_BP_DIASTOLIC, 85, "obs-bp2"),
        ],
    )
    score = preeclampsia_risk(ctx)
    assert score.level == "high"
    assert any("Observation/obs-up" in r for r in score.cited_references)
