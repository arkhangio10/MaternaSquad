"""FHIR pregnancy context aggregation tool.

Pulls everything needed for downstream agents to reason about a pregnant
patient: demographics, conditions, observations (BP, weight, A1C, urine
protein), medications, encounters, and care plans.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mcp_server.src.fhir.client import FhirClient
from mcp_server.src.sharp.context import SharpContext

# LOINC codes commonly used in pregnancy monitoring.
LOINC_BP_SYSTOLIC = "8480-6"
LOINC_BP_DIASTOLIC = "8462-4"
LOINC_BMI = "39156-5"
LOINC_BODY_WEIGHT = "29463-7"
LOINC_A1C = "4548-4"
LOINC_FASTING_GLUCOSE = "1558-6"
LOINC_URINE_PROTEIN = "2888-6"
LOINC_FETAL_HR = "55283-6"

# SNOMED codes for pregnancy and risk conditions.
SNOMED_PREGNANCY = "77386006"
SNOMED_PREECLAMPSIA = "398254007"
SNOMED_GDM = "11687002"
SNOMED_PRETERM_HISTORY = "1156871001"
SNOMED_HYPERTENSION = "38341003"

VITALS_LOINC_CODES = ",".join(
    [
        LOINC_BP_SYSTOLIC,
        LOINC_BP_DIASTOLIC,
        LOINC_BMI,
        LOINC_BODY_WEIGHT,
        LOINC_A1C,
        LOINC_FASTING_GLUCOSE,
        LOINC_URINE_PROTEIN,
        LOINC_FETAL_HR,
    ]
)


class PregnancyContext(BaseModel):
    """Aggregated pregnancy context for a Patient."""

    patient_id: str
    patient_summary: dict[str, Any] = Field(default_factory=dict)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    medications: list[dict[str, Any]] = Field(default_factory=list)
    care_plans: list[dict[str, Any]] = Field(default_factory=list)
    encounters: list[dict[str, Any]] = Field(default_factory=list)
    cited_references: list[str] = Field(
        default_factory=list, description="Resource references collected for grounding"
    )


async def get_pregnancy_context(ctx: SharpContext, lookback_days: int = 365) -> PregnancyContext:
    """Aggregate FHIR resources relevant to a pregnant patient."""
    async with FhirClient(ctx) as fhir:
        patient = await fhir.read("Patient", ctx.patient_id)

        conditions = await fhir.search(
            "Condition",
            {"patient": ctx.patient_id, "_sort": "-recorded-date"},
        )
        observations = await fhir.search(
            "Observation",
            {
                "patient": ctx.patient_id,
                "code": VITALS_LOINC_CODES,
                "_sort": "-date",
                "_count": "200",
            },
        )
        medications = await fhir.search(
            "MedicationRequest",
            {"patient": ctx.patient_id, "_sort": "-authoredon"},
        )
        care_plans = await fhir.search(
            "CarePlan",
            {"patient": ctx.patient_id, "status": "active,draft"},
        )
        encounters = await fhir.search(
            "Encounter",
            {"patient": ctx.patient_id, "_sort": "-date", "_count": "20"},
        )

        cited = [fhir.reference(patient)]
        cited += [fhir.reference(r) for r in conditions]
        cited += [fhir.reference(r) for r in observations]
        cited += [fhir.reference(r) for r in medications]
        cited += [fhir.reference(r) for r in care_plans]

        return PregnancyContext(
            patient_id=ctx.patient_id,
            patient_summary={
                "id": patient.get("id"),
                "gender": patient.get("gender"),
                "birthDate": patient.get("birthDate"),
                "communication": patient.get("communication", []),
            },
            conditions=conditions,
            observations=observations,
            medications=medications,
            care_plans=care_plans,
            encounters=encounters,
            cited_references=cited,
        )
