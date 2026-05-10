# MaternaSquad Architecture

## One-liner

Five A2A agents share one MCP server. SHARP context propagates across every hop. All clinical reasoning is grounded in FHIR R4 resources with citations to ACOG, USPSTF, ADA, and CDC published guidelines.

## High-level diagram

```
                     CLINICIAN  (Prompt Opinion workspace)
                              |
                              v
              +-------- ORCHESTRATOR (8001) --------+
              |          plans + routes              |
              v                                      v
     +--------+--------+                  +----------+----------+
     | RISK AGENT 8002 |                  | COVERAGE AGENT 8003 |
     | ACOG/USPSTF     |                  | Da Vinci PAS-shaped |
     | risk scoring    |                  | evidence packets    |
     +--------+--------+                  +----------+----------+
              |                                      |
              v                                      v
     +--------+--------+                  +----------+----------+
     | EDUCATION 8004  |                  | POSTPARTUM WATCH    |
     | multilingual    |                  | 8005, CDC Hear Her  |
     | teach-back      |                  | symptom triage      |
     +--------+--------+                  +----------+----------+
              \                                    /
               \                                  /
                v                                v
              +---------------------------------+
              |  MaternaSquad MCP Server (8080) |
              |   - fhir_get_pregnancy_context  |
              |   - acog_preeclampsia_risk      |
              |   - acog_gdm_risk               |
              |   - acog_preterm_birth_risk     |
              |   - patient_translate_message   |
              |   - patient_warning_signs_card  |
              |   - postpartum_triage           |
              |   - pa_draft_evidence_packet    |
              |   - healthcheck                 |
              +-----------+---------------------+
                          |
                          v
              +-----------+---------------------+
              |  HAPI FHIR R4 Server (8090)     |
              |   loaded with Synthea bundles   |
              +---------------------------------+
```

## Why a shared MCP, not per-agent tools

The same FHIR aggregation logic, the same risk scorers, the same translation prompts get reused across multiple agents. Centralizing them in the MCP server keeps the audit trail consistent (one place writes audit entries), keeps the FHIR client connection pool warm, and makes the Marketplace footprint cleaner: 1 MCP + 5 agents = 6 listings, all pointing at the same underlying skill set.

## SHARP context propagation

Every inbound request to an agent carries SHARP headers. The agent parses them once, then forwards them on every outbound MCP tool call and every A2A sub-agent call. The MCP server parses the same headers on entry. This is how the patient identity and FHIR session stay consistent across multi-agent workflows.

If the official Prompt Opinion SHARP spec uses different header names, change them in one place: `mcp_server/src/sharp/context.py`. Everything else flows through that single source of truth.

## Audit trail

Every tool and agent invocation writes one JSON-line audit entry containing: trace_id, actor name, action, patient_id, timestamp, model_id (if LLM), short non-PHI input/output summaries, and the FHIR resource references the output is grounded in. The audit log is the receipt the clinician can read to verify every claim.

## Safety envelope (FDA SaMD)

The system is designed to satisfy the four 21st Century Cures Act non-device CDS criteria:

1. Does not analyze image, signal, or IVD pattern data.
2. Displays medical information.
3. Supports the HCP recommendation.
4. The HCP can independently review the basis of the recommendation (every claim is cited).

The Risk Agent uses deterministic rule-based scorers. Claude provides narrative interpretation only, never an autonomous risk number. The Postpartum Watch Agent classifies against the published CDC Hear Her checklist; it does not run a predictive model.

## Data flow for the demo

1. Clinician opens Prompt Opinion workspace, selects patient (Synthea persona).
2. SHARP context is built from the workspace state (patient_id, FHIR URL, locale).
3. Clinician asks a natural-language question.
4. Orchestrator routes to one or more sub-agents.
5. Each sub-agent calls MCP tools as needed, all with the same SHARP context.
6. Outputs are merged into a clinician-facing summary with FHIR citations.
7. Audit log captures every step.

## Technology choices

- **Python 3.11** for backend. Mature library ecosystem for FHIR and async I/O.
- **FastMCP 2.x** for the MCP server. Streamable HTTP transport works for both Cloud Run and local dev.
- **FastAPI** for A2A agents with an ADK-compatible contract (base wrapper in `_base.py`).
- **Claude Sonnet 4.6 via Anthropic API** for all LLM reasoning. Extended thinking for clinical accuracy, tool use for structured outputs.
- **HAPI FHIR R4** in Docker locally. Cloud Run for production demo.
- **Synthea** for synthetic personas. No real PHI ever.
- **httpx** for FHIR calls (async, retry via tenacity).
- **Pydantic v2** for every cross-boundary data shape.
- **structlog** for structured JSON logs.

## Where this could go

- Wire the Orchestrator into a planning loop using Gemini tool calling instead of keyword routing.
- Add a longitudinal-memory tool that summarizes the patient's care plan deltas across visits.
- Add a doula-companion agent for non-clinical support, with a clear handoff to clinical agents.
- Connect to a real EHR via SMART on FHIR for a pilot.
