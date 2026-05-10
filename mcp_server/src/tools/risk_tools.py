"""Risk stratification tools grounded in published ACOG guidelines.

These are deterministic rule-based scorers backed by ACOG Practice Bulletins.
GenAI is used in `risk_agent` to interpret context and generate narrative
explanations; the actual risk score logic stays here, traceable and auditable.

References:
- ACOG Practice Bulletin No. 222 (2020) Gestational Hypertension and Preeclampsia
- ACOG Practice Bulletin No. 234 (2021) Pregestational and Gestational Diabetes
- USPSTF Aspirin Use to Prevent Preeclampsia (2021)
- ACOG Practice Bulletin No. 232 (2021) Preterm Labor

Update these references when ACOG publishes newer bulletins.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mcp_server.src.tools.fhir_tools import (
    LOINC_A1C,
    LOINC_BP_DIASTOLIC,
    LOINC_BP_SYSTOLIC,
    LOINC_BMI,
    LOINC_URINE_PROTEIN,
    SNOMED_GDM,
    SNOMED_PREECLAMPSIA,
    SNOMED_PRETERM_HISTORY,
    PregnancyContext,
)


class RiskFactor(BaseModel):
    name: str
    present: bool
    value: float | str | None = None
    cited: list[str] = Field(default_factory=list, description="FHIR refs grounding this factor")
    source: str = Field(..., description="ACOG/USPSTF guideline citation")


class RiskScore(BaseModel):
    risk_label: str  # 'preeclampsia' | 'gdm' | 'preterm_birth'
    level: str  # 'low' | 'moderate' | 'high'
    score_text: str  # human-readable explanation
    factors: list[RiskFactor]
    recommendations: list[str]
    cited_references: list[str]
    guideline_source: str


def _latest_value(observations: list[dict[str, Any]], loinc: str) -> tuple[float | None, str | None]:
    """Return (value, reference) for the most recent observation matching a LOINC code."""
    for obs in observations:
        codings = obs.get("code", {}).get("coding", []) or []
        if any(c.get("system") == "http://loinc.org" and c.get("code") == loinc for c in codings):
            value = obs.get("valueQuantity", {}).get("value")
            if isinstance(value, (int, float)):
                return float(value), f"Observation/{obs['id']}"
    return None, None


def _has_condition(conditions: list[dict[str, Any]], snomed: str) -> tuple[bool, str | None]:
    for cond in conditions:
        codings = cond.get("code", {}).get("coding", []) or []
        if any(c.get("system") == "http://snomed.info/sct" and c.get("code") == snomed for c in codings):
            return True, f"Condition/{cond['id']}"
    return False, None


def preeclampsia_risk(ctx: PregnancyContext) -> RiskScore:
    """USPSTF and ACOG aspirin-prevention preeclampsia risk model.

    HIGH risk if any one major factor: prior preeclampsia, multifetal gestation,
    chronic hypertension, type 1 or type 2 diabetes, kidney disease, autoimmune.

    MODERATE if two or more moderate factors: nulliparity, obesity (BMI > 30),
    family history, sociodemographic, age >= 35, prior pregnancy with adverse
    outcome.

    Source: USPSTF Aspirin Use 2021; ACOG Practice Bulletin No. 222 (2020).
    """
    factors: list[RiskFactor] = []
    cited: list[str] = []

    # Major: prior preeclampsia
    has_prior_pe, ref = _has_condition(ctx.conditions, SNOMED_PREECLAMPSIA)
    if ref:
        cited.append(ref)
    factors.append(
        RiskFactor(
            name="prior_preeclampsia",
            present=has_prior_pe,
            cited=[ref] if ref else [],
            source="USPSTF Aspirin 2021",
        )
    )

    # BP elevation (most recent reading)
    sbp, sbp_ref = _latest_value(ctx.observations, LOINC_BP_SYSTOLIC)
    dbp, dbp_ref = _latest_value(ctx.observations, LOINC_BP_DIASTOLIC)
    bp_high = (sbp is not None and sbp >= 140) or (dbp is not None and dbp >= 90)
    bp_refs = [r for r in [sbp_ref, dbp_ref] if r]
    cited += bp_refs
    factors.append(
        RiskFactor(
            name="hypertension_present",
            present=bp_high,
            value=f"{sbp}/{dbp}" if sbp and dbp else None,
            cited=bp_refs,
            source="ACOG PB 222 (2020)",
        )
    )

    # BMI > 30
    bmi, bmi_ref = _latest_value(ctx.observations, LOINC_BMI)
    bmi_high = bmi is not None and bmi > 30
    if bmi_ref:
        cited.append(bmi_ref)
    factors.append(
        RiskFactor(
            name="obesity_bmi_over_30",
            present=bmi_high,
            value=bmi,
            cited=[bmi_ref] if bmi_ref else [],
            source="USPSTF Aspirin 2021",
        )
    )

    # Urine protein
    upr, upr_ref = _latest_value(ctx.observations, LOINC_URINE_PROTEIN)
    proteinuria = upr is not None and upr > 0.3
    if upr_ref:
        cited.append(upr_ref)
    factors.append(
        RiskFactor(
            name="proteinuria",
            present=proteinuria,
            value=upr,
            cited=[upr_ref] if upr_ref else [],
            source="ACOG PB 222 (2020)",
        )
    )

    # Decision
    major = [f for f in factors if f.name in {"prior_preeclampsia"} and f.present]
    moderate = [f for f in factors if f.name in {"hypertension_present", "obesity_bmi_over_30"} and f.present]

    if major or proteinuria:
        level = "high"
        score_text = "High risk per USPSTF aspirin-prevention model. At least one major factor present."
        recs = [
            "Recommend low-dose aspirin 81 mg daily after 12 weeks if not contraindicated.",
            "Weekly BP monitoring.",
            "Confirm with treating obstetrician.",
        ]
    elif len(moderate) >= 2:
        level = "moderate"
        score_text = "Moderate risk: 2+ moderate factors (USPSTF 2021)."
        recs = [
            "Discuss low-dose aspirin 81 mg daily after 12 weeks.",
            "Standard schedule of BP and urine protein monitoring.",
        ]
    else:
        level = "low"
        score_text = "Low risk per USPSTF 2021."
        recs = ["Routine prenatal care."]

    return RiskScore(
        risk_label="preeclampsia",
        level=level,
        score_text=score_text,
        factors=factors,
        recommendations=recs,
        cited_references=cited,
        guideline_source="USPSTF Aspirin Use 2021; ACOG Practice Bulletin No. 222 (2020)",
    )


def gdm_risk(ctx: PregnancyContext) -> RiskScore:
    """Gestational diabetes risk per ACOG PB 234 (2021) and ADA criteria."""
    factors: list[RiskFactor] = []
    cited: list[str] = []

    has_gdm_history, ref = _has_condition(ctx.conditions, SNOMED_GDM)
    if ref:
        cited.append(ref)
    factors.append(
        RiskFactor(
            name="prior_gdm",
            present=has_gdm_history,
            cited=[ref] if ref else [],
            source="ACOG PB 234 (2021)",
        )
    )

    bmi, bmi_ref = _latest_value(ctx.observations, LOINC_BMI)
    bmi_high = bmi is not None and bmi >= 30
    if bmi_ref:
        cited.append(bmi_ref)
    factors.append(
        RiskFactor(
            name="obesity_bmi_over_30",
            present=bmi_high,
            value=bmi,
            cited=[bmi_ref] if bmi_ref else [],
            source="ACOG PB 234 (2021)",
        )
    )

    a1c, a1c_ref = _latest_value(ctx.observations, LOINC_A1C)
    a1c_elevated = a1c is not None and a1c >= 5.7
    if a1c_ref:
        cited.append(a1c_ref)
    factors.append(
        RiskFactor(
            name="prediabetic_a1c",
            present=a1c_elevated,
            value=a1c,
            cited=[a1c_ref] if a1c_ref else [],
            source="ADA Standards of Care 2024",
        )
    )

    if has_gdm_history or a1c_elevated:
        level = "high"
        score_text = "High GDM risk: prior GDM or A1C >= 5.7%."
        recs = [
            "Early glucose tolerance testing in first trimester.",
            "Refer to maternal fetal medicine if GTT abnormal.",
        ]
    elif bmi_high:
        level = "moderate"
        score_text = "Moderate GDM risk based on BMI."
        recs = ["Standard 24-28 week glucose tolerance test."]
    else:
        level = "low"
        score_text = "Low GDM risk."
        recs = ["Routine 24-28 week GTT."]

    return RiskScore(
        risk_label="gdm",
        level=level,
        score_text=score_text,
        factors=factors,
        recommendations=recs,
        cited_references=cited,
        guideline_source="ACOG Practice Bulletin No. 234 (2021); ADA Standards 2024",
    )


def preterm_birth_risk(ctx: PregnancyContext) -> RiskScore:
    """Preterm birth risk per ACOG PB 232 (2021)."""
    factors: list[RiskFactor] = []
    cited: list[str] = []

    history, ref = _has_condition(ctx.conditions, SNOMED_PRETERM_HISTORY)
    if ref:
        cited.append(ref)
    factors.append(
        RiskFactor(
            name="prior_preterm_birth",
            present=history,
            cited=[ref] if ref else [],
            source="ACOG PB 232 (2021)",
        )
    )

    if history:
        level = "high"
        score_text = "High preterm birth risk due to prior preterm history."
        recs = [
            "Consider 17-OHPC injections (ACOG PB 232).",
            "Cervical length surveillance every 2 weeks 16-24 wk.",
            "Refer to maternal fetal medicine.",
        ]
    else:
        level = "low"
        score_text = "No high-risk preterm birth factors identified in available chart."
        recs = ["Routine prenatal screening."]

    return RiskScore(
        risk_label="preterm_birth",
        level=level,
        score_text=score_text,
        factors=factors,
        recommendations=recs,
        cited_references=cited,
        guideline_source="ACOG Practice Bulletin No. 232 (2021)",
    )
