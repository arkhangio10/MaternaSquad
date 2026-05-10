"""Async FHIR R4 client for MaternaSquad.

Built on httpx. Designed for read-only access during the hackathon. Writes are
explicitly opt-in to keep the agents in a draft-only posture.
"""
from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from mcp_server.src.sharp.context import SharpContext

log = structlog.get_logger(__name__)


class FhirClient:
    """Read-mostly FHIR R4 client.

    Usage:
        async with FhirClient(ctx) as fhir:
            patient = await fhir.read("Patient", ctx.patient_id)
            obs = await fhir.search("Observation", {"patient": ctx.patient_id})
    """

    def __init__(self, ctx: SharpContext, *, timeout_s: float = 10.0):
        self.ctx = ctx
        self._client: httpx.AsyncClient | None = None
        self._timeout_s = timeout_s

    async def __aenter__(self) -> FhirClient:
        headers = {"Accept": "application/fhir+json"}
        if self.ctx.fhir_access_token:
            headers["Authorization"] = f"Bearer {self.ctx.fhir_access_token}"
        self._client = httpx.AsyncClient(
            base_url=self.ctx.fhir_server_url.rstrip("/"),
            headers=headers,
            timeout=self._timeout_s,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def _c(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("FhirClient not entered. Use `async with FhirClient(ctx) as f:`.")
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    async def read(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        """Read a single FHIR resource by type and ID."""
        url = f"/{resource_type}/{resource_id}"
        log.info("fhir.read", resource_type=resource_type, resource_id=resource_id)
        r = await self._c.get(url)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    async def search(
        self,
        resource_type: str,
        params: dict[str, str] | None = None,
        count: int = 100,
    ) -> list[dict[str, Any]]:
        """Search FHIR resources. Returns the list of resources, not the Bundle."""
        params = dict(params or {})
        params.setdefault("_count", str(count))
        url = f"/{resource_type}"
        log.info("fhir.search", resource_type=resource_type, params=params)
        r = await self._c.get(url, params=params)
        r.raise_for_status()
        bundle = r.json()
        entries = bundle.get("entry", []) or []
        return [e["resource"] for e in entries if "resource" in e]

    async def history(
        self, resource_type: str, resource_id: str, count: int = 10
    ) -> list[dict[str, Any]]:
        """Read version history for a resource. Useful for showing what changed."""
        url = f"/{resource_type}/{resource_id}/_history"
        r = await self._c.get(url, params={"_count": str(count)})
        r.raise_for_status()
        bundle = r.json()
        entries = bundle.get("entry", []) or []
        return [e["resource"] for e in entries if "resource" in e]

    def reference(self, resource: dict[str, Any]) -> str:
        """Return the canonical reference string for a resource, e.g. 'Observation/abc'."""
        return f"{resource['resourceType']}/{resource['id']}"
