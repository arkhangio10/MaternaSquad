# MaternaSquad

> Five A2A agents collaborating around one mother to reduce preventable maternal morbidity and mortality.

Built for the **Agents Assemble Healthcare AI Endgame Challenge** by Prompt Opinion. Submission deadline 2026-05-11 23:00 EDT.

In the United States, a woman dies in pregnancy or postpartum every 12 hours. **80 percent of those deaths are preventable** (CDC, 2024). MaternaSquad is a five-agent squad that collaborates around one patient: it stratifies risk per ACOG and USPSTF, drafts prior-authorization packets shaped to the Da Vinci PAS implementation guide, generates patient-facing education at grade 5 reading level in the patient's language, and triages postpartum symptoms against the CDC Hear Her warning signs.

Every clinical claim cites a FHIR R4 resource. Every recommendation cites a published guideline. Demo data is Synthea synthetic, never real PHI.

---

## Architecture

```
                     CLINICIAN  (Prompt Opinion workspace)
                              |
                              v
              +-------- ORCHESTRATOR (Cloud Run) -----+
              |          plans + routes               |
              v                                       v
     +--------+--------+                  +-----------+----------+
     | RISK AGENT      |                  | COVERAGE AGENT       |
     | ACOG/USPSTF     |                  | Da Vinci PAS-shaped  |
     | risk scoring    |                  | evidence packets     |
     +--------+--------+                  +-----------+----------+
              |                                       |
              v                                       v
     +--------+--------+                  +-----------+----------+
     | EDUCATION       |                  | POSTPARTUM WATCH     |
     | multilingual    |                  | CDC Hear Her         |
     | teach-back      |                  | symptom triage       |
     +--------+--------+                  +-----------+----------+
              \                                     /
               \                                   /
                v                                 v
              +---------------------------------+
              |  MaternaSquad MCP Server        |
              |  (FastMCP, 8 clinical tools)    |
              +---------+-----------------------+
                        |
                        v
              +---------+-----------------------+
              |  HAPI FHIR R4 Server            |
              |  loaded with Synthea bundles    |
              +---------------------------------+
```

Five A2A agents share one MCP server. SHARP context propagates across every hop. All clinical reasoning is grounded in FHIR R4 resources with citations to ACOG, USPSTF, ADA, and CDC published guidelines.

## Live deployment (Google Cloud Run, region europe-west4)

| Service | URL |
|---|---|
| Orchestrator (entry point) | https://maternasquad-orchestrator-mdf575wm2q-ez.a.run.app |
| MCP server | https://maternasquad-mcp-mdf575wm2q-ez.a.run.app |
| Risk agent | https://maternasquad-risk-agent-mdf575wm2q-ez.a.run.app |
| Coverage agent | https://maternasquad-coverage-agent-mdf575wm2q-ez.a.run.app |
| Education agent | https://maternasquad-education-agent-mdf575wm2q-ez.a.run.app |
| Postpartum watch | https://maternasquad-postpartum-watch-mdf575wm2q-ez.a.run.app |
| HAPI FHIR R4 | https://maternasquad-hapi-mdf575wm2q-ez.a.run.app |

Every agent serves an A2A protocol agent card at `/.well-known/agent-card.json`. The MCP server is registered in Prompt Opinion under Configuration → MCP Servers; the 5 A2A agents under Agents → External Agents.

## Stack

- **Language**: Python 3.11
- **LLM**: Claude Sonnet 4.6 via Anthropic API. Adaptive thinking for narratives, forced tool use for typed outputs.
- **MCP**: FastMCP 3.x, `streamable-http` transport, served at `/mcp`.
- **A2A**: FastAPI agents with the A2A v0.2 agent card published at `/.well-known/agent-card.json`.
- **FHIR**: R4 only. HAPI FHIR R4 in Docker locally and on Cloud Run.
- **Synthetic data**: Synthea, with a custom maternal-care module.
- **Deploy**: Cloud Build pipeline (`infrastructure/cloudbuild.yaml`) plus an idempotent prereq script (`infrastructure/deploy.ps1`).
- **Auth**: Application Default Credentials locally, Secret Manager for `ANTHROPIC_API_KEY` on Cloud Run.

## Demo personas (Synthea synthetic, no real PHI)

Three patients are loaded into HAPI on Cloud Run:

- **Patient/1076** - Cordelia (Detroit, BMI 30.55, preeclampsia case). The demo star.
- **Patient/2218** - Yuri (Houston, gestational diabetes, Spanish locale). Shows the multilingual education flow.
- **Patient/1569** - Cyndi (rural Kentucky, postpartum mental health, age 20). Shows the postpartum surveillance flow.

## How it works

1. The clinician opens the Prompt Opinion workspace and selects a Synthea patient.
2. SHARP context is built from the workspace state (patient_id, FHIR URL, locale).
3. The clinician asks a natural-language question.
4. The Orchestrator plans which sub-agents are relevant (deliberately keyword-based and LLM-free for speed) and invokes them in parallel.
5. Each sub-agent calls the MCP server, which calls HAPI FHIR for chart context plus deterministic ACOG/USPSTF rule-based scorers for risk numbers.
6. Sub-agent outputs are merged into a 4 to 6 sentence clinician handoff with inline `[ResourceType/id]` citations.
7. Every step writes a JSON-line audit entry. The clinician can read the receipt for every claim.

## Safety envelope (FDA SaMD)

Designed to satisfy the four 21st Century Cures Act non-device CDS criteria:

1. Does not analyze image, signal, or IVD pattern data.
2. Displays medical information.
3. Supports the HCP recommendation.
4. The HCP can independently review the basis of the recommendation (every claim is cited).

Risk numbers come from deterministic rule-based scorers. Claude provides narrative interpretation only, never an autonomous risk model. The Postpartum Watch Agent classifies against the published CDC Hear Her checklist; it does not run a predictive model. No prescribing. No autonomous submission to payers.

## Repository structure

```
maternasquad/
  a2a_agents/          # 5 A2A agents (FastAPI, ADK-compatible contract)
    _base.py           # shared scaffolding + agent-card endpoint + call_mcp_tool
    orchestrator/      # plan, route, merge sub-agent outputs
    risk_agent/        # ACOG/USPSTF/ADA risk scoring
    coverage_agent/    # Da Vinci PAS evidence packets
    education_agent/   # multilingual patient teach-back
    postpartum_watch/  # CDC Hear Her triage
  mcp_server/          # FastMCP server with 8 clinical tools + healthcheck
    src/server.py
    src/sharp/         # SHARP context propagation
    src/tools/
    src/audit.py       # JSON-line audit writer
    src/gemini.py      # Anthropic Claude wrapper (filename kept for import compat)
  synthea/             # custom Synthea maternal-care module + load script
  infrastructure/
    cloudbuild.yaml    # 9-step Cloud Build pipeline
    deploy.ps1         # idempotent deploy + IAM + secret prereq
    Dockerfile.mcp
    Dockerfile.agent
  scripts/             # local stack runners (start_hapi, run_mcp, run_agents, smoke_test)
  docs/
    ARCHITECTURE.md         # design decisions + tradeoffs
    DEMO_SCRIPT.md          # 3-minute video script
    MARKETPLACE_LISTINGS.md # paste-sheet for Prompt Opinion Marketplace
  pyproject.toml
  requirements.txt     # mirrors pyproject for the production Docker image
  .env.example
```

## Prerequisites

- Windows + PowerShell (most scripts are .ps1; the Python is OS-agnostic)
- Python 3.11
- Docker Desktop
- An Anthropic API key (for `ANTHROPIC_API_KEY`)
- Optional for deploy: gcloud SDK, Java 17 for Synthea regeneration

## How to run locally

```powershell
# 1. Activate venv
.\.venv\Scripts\Activate.ps1

# 2. Set ANTHROPIC_API_KEY in .env (copy from .env.example first)
Copy-Item .env.example .env
notepad .env

# 3. Bring up HAPI FHIR locally
.\scripts\start_hapi.ps1

# 4. Generate Synthea bundles and load them
.\synthea\generate_personas.ps1
.\synthea\load_to_hapi.ps1

# 5. Run the MCP server (terminal A)
.\scripts\run_mcp.ps1

# 6. Run all 5 A2A agents (spawns 5 PS windows)
.\scripts\run_agents.ps1

# 7. End-to-end smoke against a known local patient
.\scripts\smoke_test.ps1 2047
```

## How to deploy to Cloud Run

```powershell
# Sets up Artifact Registry, Secret Manager, IAM, then submits Cloud Build.
.\infrastructure\deploy.ps1

# After every deploy, re-grant public access (the cloud-sdk Cloud Build step
# silently drops --allow-unauthenticated; the build's compute SA cannot
# setIamPolicy, so this loop runs locally):
foreach ($svc in @(
    "maternasquad-hapi","maternasquad-mcp","maternasquad-orchestrator",
    "maternasquad-risk-agent","maternasquad-coverage-agent",
    "maternasquad-education-agent","maternasquad-postpartum-watch"
)) {
    gcloud run services add-iam-policy-binding $svc `
        --region=europe-west4 --project=maternasquad `
        --member="allUsers" --role="roles/run.invoker" --quiet | Out-Null
}
```

## End-to-end smoke against the live deployment

```bash
curl -s -X POST "https://maternasquad-orchestrator-mdf575wm2q-ez.a.run.app/invoke" \
  -H "Content-Type: application/json" \
  -H "X-SHARP-Patient-Id: 1076" \
  -H "X-SHARP-FHIR-Server-URL: https://maternasquad-hapi-mdf575wm2q-ez.a.run.app/fhir" \
  -H "X-SHARP-User-Role: clinician" \
  -H "X-SHARP-Trace-Id: smoke-001" \
  -H "X-SHARP-Locale: en-US" \
  --data '{"user_message":"Set up this patient for the third trimester. She has been complaining about headaches.","context":{}}'
```

The response includes a `plan`, per-agent structured outputs, a `clinician_summary` with inline FHIR citations, and a `cited_references` union list.

## Hackathon submission

- **Devpost**: https://agents-assemble.devpost.com/
- **Demo video** (under 3 min): script in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)
- **Marketplace listings copy**: [docs/MARKETPLACE_LISTINGS.md](docs/MARKETPLACE_LISTINGS.md)
- **Architecture deep-dive**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Judges this is meant for**: Josh Mandel (FHIR), Alice Zheng (women's health VC), Stephon Proctor (CHOP), Piyush Mathur (ICU), Joshua Hickey (Mayo), Parth Tripathi (Vertex AI).

## License

MIT for the hackathon. Synthea is Apache 2.0. HAPI FHIR is Apache 2.0. ACOG and USPSTF guidelines are cited inline; the rule-based scorers reproduce the published criteria. CDC Hear Her warning signs are public-domain per cdc.gov.
