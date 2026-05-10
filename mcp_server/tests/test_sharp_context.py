"""Tests for SHARP context parsing and propagation."""
from __future__ import annotations

import pytest

from mcp_server.src.sharp.context import (
    HEADER_FHIR_ACCESS_TOKEN,
    HEADER_FHIR_SERVER_URL,
    HEADER_LOCALE,
    HEADER_PATIENT_ID,
    HEADER_TRACE_ID,
    HEADER_USER_ROLE,
    SharpContext,
)


def test_context_serializes_required_headers() -> None:
    ctx = SharpContext(
        patient_id="patient-123",
        fhir_server_url="http://localhost:8090/fhir",
    )
    headers = ctx.to_headers()
    assert headers[HEADER_PATIENT_ID] == "patient-123"
    assert headers[HEADER_FHIR_SERVER_URL] == "http://localhost:8090/fhir"
    assert headers[HEADER_USER_ROLE] == "clinician"
    assert headers[HEADER_LOCALE] == "en-US"
    assert HEADER_TRACE_ID in headers


def test_context_includes_optional_headers_when_set() -> None:
    ctx = SharpContext(
        patient_id="patient-123",
        fhir_server_url="http://localhost:8090/fhir",
        fhir_access_token="bearer-abc",
        encounter_id="enc-99",
        locale="es-US",
    )
    headers = ctx.to_headers()
    assert headers[HEADER_FHIR_ACCESS_TOKEN] == "bearer-abc"
    assert headers[HEADER_LOCALE] == "es-US"


def test_context_round_trips_through_headers() -> None:
    original = SharpContext(
        patient_id="aisha-001",
        fhir_server_url="http://localhost:8090/fhir",
        locale="es-US",
        user_role="patient",
    )
    parsed = SharpContext.from_headers(original.to_headers())
    assert parsed.patient_id == original.patient_id
    assert parsed.fhir_server_url == original.fhir_server_url
    assert parsed.locale == "es-US"
    assert parsed.user_role == "patient"
    assert parsed.trace_id == original.trace_id


def test_context_parses_case_insensitive_headers() -> None:
    headers = {
        "x-sharp-patient-id": "p1",
        "X-Sharp-Fhir-Server-URL": "http://localhost:8090/fhir",
    }
    ctx = SharpContext.from_headers(headers)
    assert ctx.patient_id == "p1"


def test_context_raises_on_missing_required_headers() -> None:
    with pytest.raises(ValueError, match="Missing required SHARP headers"):
        SharpContext.from_headers({})
