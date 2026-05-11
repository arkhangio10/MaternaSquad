# MaternaSquad

### Technical Brief and Architecture Reference

**Hackathon submission**: Agents Assemble Healthcare AI Endgame Challenge by Prompt Opinion
**Author**: Abel Mancilla Montesinos (arkhangio@gmail.com)
**Repository**: https://github.com/arkhangio10/MaternaSquad
**Marketplace listing**: https://app.promptopinion.ai/marketplace/mcp/019e1092-1eb3-7d0b-b0e9-d45c3b499482
**Submission date**: 2026-05-11

---

## 1. Executive summary

MaternaSquad is a five-agent maternal-care system that runs on the Prompt Opinion platform with a shared Model Context Protocol (MCP) toolbox. It coordinates a clinical workflow around one pregnant or postpartum patient: risk stratification per ACOG and USPSTF, Da Vinci PAS-shaped prior-authorization drafts, multilingual patient education at grade 5 reading level, postpartum CDC Hear Her symptom triage with SBAR escalation, and a clinician-facing handoff.

Three design invariants:

1. Every clinical claim cites a FHIR R4 resource inline as `[ResourceType/id]`.
2. Risk numbers come from deterministic rule-based scorers, never autonomous LLM output.
3. The system supports the four 21st Century Cures Act non-device CDS criteria so it stays out of FDA SaMD territory.

The squad is registered on the Prompt Opinion marketplace as one MCP server, five External A2A agents, and one Prompt Opinion native BYO agent that serves as the chat entry point.

---

## 2. The problem

The United States has the worst maternal mortality rate in the developed world. CDC data:

- A pregnancy- or postpartum-related death occurs every 12 hours.
- 80 percent of those deaths are preventable.
- The largest share happens in the first 12 weeks postpartum, often at home, sometimes at night, sometimes without language support.

By the time a clinician is reached, hours are lost. The contributing failures are well documented and shared across systems: signals are missed in the chart, prior authorization delays surveillance equipment, patients do not read the language of the discharge instructions, postpartum warning signs go untriaged, and audit trails for clinical decisions are weak.

MaternaSquad does not claim to solve maternal mortality. It addresses one workflow gap: the clinician needs a multi-specialist decision-support layer that produces cited drafts in seconds, in the patient's language, with safety constraints baked in.

---

## 3. The solution

Five A2A specialist agents collaborating around one mother, sharing one MCP toolbox.

| Agent | Specialty | Calls into MCP |
|---|---|---|
| Orchestrator | Plans, routes, merges, produces clinician handoff | All tools as needed |
| Risk Agent | Preeclampsia / GDM / preterm risk per ACOG, USPSTF, ADA | `acog_preeclampsia_risk`, `acog_gdm_risk`, `acog_preterm_birth_risk` |
| Coverage Agent | Drafts prior-auth packets shaped to HL7 Da Vinci PAS | `pa_draft_evidence_packet` |
| Education Agent | Multilingual patient teach-back, grade 5, FHIR-cited | `patient_translate_message`, `patient_warning_signs_card` |
| Postpartum Watch | CDC Hear Her symptom triage with SBAR drafts | `postpartum_triage` |

One MCP server exposes eight clinical tools plus a healthcheck. The same MCP is called by all five agents through the Prompt Opinion FHIR Context Extension, with least-privilege SMART scopes.

A native Prompt Opinion BYO agent named MaternaSquad Care Coordinator serves as the chat entry point in the workspace. It loads our published Agent Skill (`maternasquad-care`) and the MaternaSquad MCP, both registered on the Prompt Opinion marketplace.

---

## 4. Architecture

```
                  CLINICIAN  (Prompt Opinion workspace)
                            |
                            v
            +-------- BYO Care Coordinator -------+
            |  loaded with maternasquad-care      |
            |  skill + MaternaSquad MCP tools     |
            +-------------------------------------+
                            |
              consults via A2A (optional)
                            v
            +-------- ORCHESTRATOR (Cloud Run) ---+
            |        plans + routes                |
            v                                      v
   +--------+--------+                  +----------+----------+
   | RISK AGENT      |                  | COVERAGE AGENT      |
   | ACOG/USPSTF     |                  | Da Vinci PAS-shaped |
   | risk scoring    |                  | evidence packets    |
   +--------+--------+                  +----------+----------+
            |                                      |
            v                                      v
   +--------+--------+                  +----------+----------+
   | EDUCATION       |                  | POSTPARTUM WATCH    |
   | multilingual    |                  | CDC Hear Her        |
   | teach-back      |                  | symptom triage      |
   +--------+--------+                  +----------+----------+
            \                                    /
             \                                  /
              v                                v
            +---------------------------------+
            |  MaternaSquad MCP Server        |
            |  (FastMCP, 8 clinical tools)    |
            +---------+-----------------------+
                      |
                      v
            +---------+-----------------------+
            |  FHIR R4 Server                 |
            |  (Prompt Opinion workspace FHIR |
            |   or HAPI FHIR for self-host)   |
            +---------------------------------+
```

### Why a shared MCP

The same FHIR aggregation logic, the same risk scorers, the same translation prompts, the same audit writer get reused across multiple agents. Centralizing them in the MCP server keeps the audit trail consistent (one place writes audit entries), keeps FHIR connections warm, and produces a cleaner marketplace footprint (one MCP listing serves all five agents).

### Context propagation

Two parallel paths into the same MCP:

- **Prompt Opinion → MCP**: when called from a Po chat (BYO Care Coordinator), Po sends `x-fhir-server-url`, `x-fhir-access-token`, `x-patient-id` HTTP headers per tool call, after the user authorizes the FHIR Context Extension scopes on connect.
- **MaternaSquad agent → MCP**: when called from one of our five A2A agents on Cloud Run, the agent forwards SHARP context headers (`X-SHARP-Patient-Id`, `X-SHARP-FHIR-Server-URL`, etc.) plus a `headers` dict on the tool call.

The MCP server normalizes both into one `SharpContext` Pydantic model in `mcp_server/src/sharp/context.py`. Tools never branch on which path called them.

---

## 5. Technology stack

- **Language**: Python 3.11
- **LLM**: Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`). Adaptive thinking for narratives. Forced `tool_choice` for Pydantic-typed structured outputs (the `thinking` parameter is dropped on forced tool calls; this is a Claude API constraint).
- **MCP framework**: FastMCP 3.x with streamable-http transport at `/mcp`.
- **A2A framework**: FastAPI agents with the A2A v0.2 protocol. Each agent serves an Agent Card at `/.well-known/agent-card.json` and an `/invoke` endpoint. The card declares `supportedInterfaces` with `protocolBinding=JSONRPC` and the FHIR Context Extension URI on the Orchestrator card.
- **FHIR**: R4 only. HAPI FHIR R4 in Docker for local development, Prompt Opinion's workspace FHIR proxy in production.
- **Synthetic data**: Synthea with custom maternal-care modules. Three demo personas: Cordelia (preeclampsia, Detroit), Yuri (gestational diabetes, Houston, Spanish), Cyndi (postpartum mental health, rural Kentucky).
- **Deploy**: 9-step Google Cloud Build pipeline (`infrastructure/cloudbuild.yaml`) with an idempotent PowerShell prereq script (`infrastructure/deploy.ps1`). Cloud Run for HAPI, MCP, and the six agent services. Artifact Registry for images. Secret Manager for `ANTHROPIC_API_KEY`.
- **Audit**: `mcp_server/src/audit.py` writes one JSON-line per tool / agent call with `trace_id`, actor, action, patient_id, model_id, input/output summaries, and the FHIR resources the output is grounded in. PHI bodies are never logged.
- **Pydantic v2** for every cross-boundary data shape.
- **structlog** for JSON-structured logging.

---

## 6. Integration with Prompt Opinion

### MCP Server registration

The MCP at `https://maternasquad-mcp-mdf575wm2q-ez.a.run.app/mcp` is registered under `Configuration → MCP Servers` and published in Marketplace Studio at:

```
https://app.promptopinion.ai/marketplace/mcp/019e1092-1eb3-7d0b-b0e9-d45c3b499482
```

### FHIR Context Extension

The MCP declares the `ai.promptopinion/fhir-context` extension in its `initialize` response so Po sends the FHIR URL, access token, and patient ID on every tool call. Implemented by monkey-patching FastMCP's `get_capabilities` because the documented `on_initialize` middleware path captures `InitializeResult` after it has been sent to the client (`fastmcp/server/low_level.py` wraps `responder.respond` in `_received_request` for `InitializeRequest`).

Extension declaration (10 SMART scopes, 3 required, 7 optional):

```json
{
  "ai.promptopinion/fhir-context": {
    "scopes": [
      {"name": "patient/Patient.rs", "required": true},
      {"name": "patient/Condition.rs", "required": true},
      {"name": "patient/Observation.rs", "required": true},
      {"name": "patient/MedicationRequest.rs"},
      {"name": "patient/MedicationStatement.rs"},
      {"name": "patient/Encounter.rs"},
      {"name": "patient/CarePlan.rs"},
      {"name": "patient/DocumentReference.rs"},
      {"name": "patient/ServiceRequest.rs"},
      {"name": "patient/Coverage.rs"}
    ]
  }
}
```

### External Agents

Five A2A agents are registered under `Agents → External Agents`:

- MaternaSquad Orchestrator
- MaternaSquad Risk Agent
- MaternaSquad Coverage Agent
- MaternaSquad Education Agent
- MaternaSquad Postpartum Watch

Each serves its Agent Card v0.2 at `/.well-known/agent-card.json` with `protocolBinding=JSONRPC`, `protocolVersion=0.2.0`, `defaultInputModes`, `defaultOutputModes`, and skills declared.

### BYO Care Coordinator

A Prompt Opinion native agent named MaternaSquad Care Coordinator is the chat entry point. It is configured with:

- Allowed contexts: Workspace, Patient
- Model: MaternaSquad Claude (the workspace's configured Claude model)
- Tools: MaternaSquad MCP attached
- Agent Skills: `maternasquad-care` SKILL.md package with four example interaction patterns
- A2A: enabled with FHIR Context Extension required, three skills declared (`third_trimester_setup`, `postpartum_triage`, `patient_education`)

When the clinician asks a question, the BYO agent loads the skill, runs the MCP tools, optionally consults an External Agent, and produces the cited clinician handoff.

---

## 7. Safety posture

### 21st Century Cures Act non-device CDS criteria

1. **No image, signal, or IVD pattern analysis.** Risk numbers come from rule-based scorers on coded FHIR resources, not from any model trained on imaging or signal data.
2. **Displays medical information.** The system surfaces ACOG, USPSTF, ADA, and CDC guidance alongside the patient's chart.
3. **Supports the HCP recommendation.** Every output is a draft. The clinician decides. No autonomous order placement, no autonomous payer submission, no autonomous prescribing.
4. **HCP can independently review the basis.** Every clinical claim cites a specific FHIR resource by ID. Every recommendation cites the published guideline by name and year. The audit log makes the chain auditable line by line.

### Code-level safety constraints

- `mcp_server/src/gemini.py:generate_text(..., require_citations=True)` rejects any LLM response that does not contain at least one `[ResourceType/id]` inline citation. Implemented via `CITATION_PATTERN` regex.
- `mcp_server/src/gemini.py:generate_structured()` uses forced `tool_choice` and Pydantic schema validation; the response is type-checked before it reaches the agent.
- Risk scorers in `mcp_server/src/tools/risk_tools.py` are pure deterministic Python — Claude never produces a numeric risk score.
- `mcp_server/src/sharp/context.py` requires patient ID and FHIR server URL before any tool runs; missing context returns a graceful error, never a fabricated answer.
- `audit.py` never logs full FHIR resource bodies; only ID, resource type, and SHARP trace ID.

### Refusal cases (in the skill prompt)

The agent refuses to:
- Give a definitive diagnosis.
- Give a specific medication dose without a guideline reference or an existing FHIR `MedicationRequest`.
- Auto-submit anything to a payer, EHR, or external system.

---

## 8. Clinical grounding

Every recommendation in MaternaSquad cites a published guideline by name and year.

| Tool / agent | Guideline citations |
|---|---|
| `acog_preeclampsia_risk` | USPSTF Aspirin Use to Prevent Preeclampsia and Related Morbidity and Mortality (2021); ACOG Practice Bulletin 222 (2020) Gestational Hypertension and Preeclampsia |
| `acog_gdm_risk` | ACOG Practice Bulletin 234 (2021); ADA Standards of Medical Care in Diabetes (2024) |
| `acog_preterm_birth_risk` | ACOG Practice Bulletin 232 (2021) Indications for Outpatient Antenatal Fetal Surveillance |
| `postpartum_triage` | CDC Hear Her, Urgent Maternal Warning Signs (https://www.cdc.gov/hearher/maternal-warning-signs/index.html); ACOG Practice Bulletin 736 |
| `pa_draft_evidence_packet` | HL7 Da Vinci Prior Authorization Support IG (https://hl7.org/fhir/us/davinci-pas/) |

The rule-based scorers reproduce the published criteria exactly. They are auditable Python functions on `mcp_server/src/tools/risk_tools.py`, not LLM heuristics.

---

## 9. Demo walkthrough

Clinician opens Prompt Opinion, selects Patient/9178f7da (Cordelia, 33, Detroit, BMI 30.55, Synthea synthetic, never real PHI), and asks the MaternaSquad Care Coordinator:

> Run the full third-trimester risk stratification on this patient. Show me the FHIR observation IDs you grounded each finding on.

The agent:

1. Loads the `maternasquad-care` skill (SKILL.md guidance for workflow, refusals, citation requirements).
2. Calls `fhir_get_pregnancy_context` on the MaternaSquad MCP. Po injects `x-fhir-server-url`, `x-fhir-access-token`, `x-patient-id` per the authorized SMART scopes. The tool queries Po's FHIR proxy for Patient, active Conditions, recent Observations, MedicationRequests, CarePlans, Encounters.
3. Calls `acog_preeclampsia_risk`, `acog_gdm_risk`, `acog_preterm_birth_risk` in parallel. Each scorer returns a structured `RiskScore` with `level` (low / moderate / high), per-factor evidence with FHIR citations, and a guideline source string.
4. Synthesizes a clinician handoff. Example real output from Cordelia's chart:
   - **GDM moderate risk** grounded in `Observation/cfa31f08-2025-4974-9b5a-8ce5756d2dd7` (BMI 30.55, 2023-06-18) per ACOG PB 234 (2021) and ADA 2024.
   - **Preeclampsia low risk** per USPSTF Aspirin 2021 and ACOG PB 222 (2020).
   - **Preterm birth low risk** per ACOG PB 232 (2021).
5. Recommends a 24-28 week glucose tolerance test, drafted for clinician approval.

Decision support only. The clinician decides.

For multilingual flow: the clinician follows up "Now generate the postpartum warning signs card for this patient in Spanish." The Education Agent generates a grade 5 Spanish card with inline `[Condition/...]` and `[Encounter/...]` citations, and an English back-translation below for verification.

---

## 10. Audit trail

Every tool and agent invocation writes one JSON line to `audit/maternasquad.log` (local) or to Cloud Logging (production):

```json
{
  "trace_id": "smoke-cloudrun-002",
  "timestamp": "2026-05-10T20:48:32Z",
  "actor": "mcp:acog_preeclampsia_risk",
  "action": "risk_score",
  "patient_id": "9178f7da-126b-4675-a91b-2ed3ee0dbe18",
  "model_id": null,
  "input_summary": "BMI 30.55, no prior preeclampsia, age 33",
  "output_summary": "level=low",
  "cited_resources": ["Observation/cfa31f08-2025-4974-9b5a-8ce5756d2dd7"]
}
```

The clinician can read this log to verify any claim, any recommendation, any guideline reference, at the resource ID level.

---

## 11. What we built (and what we learned)

### What we built in the hackathon window

- 7 Cloud Run services (HAPI FHIR, MCP server, 5 A2A agents)
- 1 BYO Prompt Opinion native agent + 1 Agent Skill SKILL.md package
- 6 Marketplace listings (5 External Agents + 1 MCP Server registered; MCP and BYO Care Coordinator published to the public marketplace)
- 9 MCP tools with FHIR R4 grounding and full citation enforcement
- 3 Synthea demo personas (Cordelia preeclampsia, Yuri Spanish GDM, Cyndi postpartum mental health)
- Complete Cloud Build deploy pipeline (idempotent, IAM-aware, secret-managed)

### Lessons learned

- FastMCP's `on_initialize` middleware cannot mutate the `InitializeResult` (the response is dispatched before the middleware sees the captured response). The escape hatch is to monkey-patch `LowLevelServer.get_capabilities`.
- PowerShell pipes to `gcloud secrets create --data-file=-` inject a trailing `\r\n` that httpx rejects as `LocalProtocolError: Illegal header value` when the SDK uses the secret as an HTTP header. Solution: write to a temp file via `[System.IO.File]::WriteAllBytes`.
- Claude's `thinking={"type":"adaptive"}` is incompatible with forced `tool_choice` and returns HTTP 400. Drop `thinking` from structured calls; keep it on free-text calls.
- The Prompt Opinion A2A Agent Card schema is strict v1 with camelCase, requires `supportedInterfaces` with `protocolBinding` + `protocolVersion`, and uses an `extensions` array (not the MCP extensions object) on `capabilities`.

---

## 12. Future work

- Wire the Orchestrator's keyword router into a planning loop with Claude tool calling for harder routing decisions.
- Add a longitudinal-memory tool that summarizes the patient's care plan deltas across visits.
- Add a doula-companion agent for non-clinical support, with a clear handoff to clinical agents.
- Connect to a real EHR via SMART on FHIR for a pilot deployment.
- Localize beyond English / Spanish — Mandarin, Arabic, Haitian Creole are the highest-impact next tongues for US maternal-care demographics.

---

## 13. References

- CDC Hear Her, Urgent Maternal Warning Signs: https://www.cdc.gov/hearher/maternal-warning-signs/index.html
- USPSTF Aspirin Use to Prevent Preeclampsia and Related Morbidity and Mortality (2021): https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/aspirin-use-to-prevent-preeclampsia-and-related-morbidity-and-mortality-preventive-medication
- ACOG Practice Bulletin 222 (2020) Gestational Hypertension and Preeclampsia
- ACOG Practice Bulletin 232 (2021) Indications for Outpatient Antenatal Fetal Surveillance
- ACOG Practice Bulletin 234 (2021)
- ACOG Practice Bulletin 736 (postpartum care)
- ADA Standards of Medical Care in Diabetes (2024)
- HL7 Da Vinci Prior Authorization Support IG: https://hl7.org/fhir/us/davinci-pas/
- FHIR R4 specification: https://hl7.org/fhir/R4/
- Anthropic Claude documentation: https://docs.anthropic.com
- FastMCP: https://gofastmcp.com/
- Synthea synthetic patient generator: https://synthetichealth.github.io/synthea/
- 21st Century Cures Act, Section 3060 (non-device CDS criteria): https://www.fda.gov/medical-devices/software-medical-device-samd/clinical-decision-support-software

---

*MaternaSquad. Five agents. One mother. Zero invented scores.*
