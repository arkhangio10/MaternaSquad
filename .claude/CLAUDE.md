# Claude Code Rules for MaternaSquad

You are an AI coding assistant working on **MaternaSquad**, a multi-agent healthcare system for the Agents Assemble Healthcare AI Endgame Challenge by Prompt Opinion. Deadline May 11, 2026. The user is competing for the Grand Prize ($7,500).

Read this file before any meaningful action on the codebase.

## The mission in one paragraph

Five A2A agents (Orchestrator, Risk, Coverage, Education, Postpartum Watch) collaborate around one mother to reduce preventable maternal morbidity and mortality. They share an MCP server with 8 clinical tools plus `healthcheck`. All hops propagate SHARP healthcare context. All clinical reasoning is grounded in FHIR R4 resources with citations. Demo data is Synthea synthetic, never real PHI.

## Stack rules (do not deviate without asking)

- Language: Python 3.11 for backend, TypeScript only if explicitly requested.
- LLM: Claude Sonnet 4.6 via Anthropic API (`claude-sonnet-4-6`). Set `ANTHROPIC_API_KEY` in `.env`. Override model with `CLAUDE_MODEL` env var. The wrapper is `mcp_server/src/gemini.py` (filename kept for import compatibility). Uses adaptive thinking + tool use for structured outputs.
- MCP framework: FastMCP 2.x or 3.x. The `pyproject.toml` pin is `>=2.0.0`. The local venv currently runs 3.2.4. The server uses `transport="streamable-http"` and serves on `/mcp`.
- A2A framework: FastAPI with ADK-compatible agent contract (SHARP headers in, structured JSON out). Keep the contract in `a2a_agents/_base.py` so a future ADK swap is mechanical.
- FHIR: R4 only (not R5, not STU3).
- Deploy target: Google Cloud Run, project `maternasquad`, region `europe-west4`.
- Auth: Application Default Credentials locally, service account on Cloud Run. `ANTHROPIC_API_KEY` stored in Secret Manager (not in env vars directly on Cloud Run).
- FHIR server (dev): HAPI FHIR R4 in Docker on localhost:8090.
- FHIR server (prod): `maternasquad-hapi` Cloud Run service (mirrored from `hapiproject/hapi:latest`, min-instances=1 so data survives the demo).
- OS: Windows + PowerShell. Never use bash-only patterns in scripts.

## GCP configuration (current)

- `GCP_PROJECT_ID=maternasquad`
- `GCP_REGION=europe-west4`
- Artifact Registry repo: `europe-west4-docker.pkg.dev/maternasquad/maternasquad/`
- Secret Manager secret: `ANTHROPIC_API_KEY`
- Cloud Run services (after deploy): `maternasquad-hapi`, `maternasquad-mcp`, `maternasquad-orchestrator`, `maternasquad-risk-agent`, `maternasquad-coverage-agent`, `maternasquad-education-agent`, `maternasquad-postpartum-watch`

## PowerShell vs bash

- Use semicolons, not `&&`. PowerShell does not chain with `&&` until very recent versions.
- Use `Remove-Item -Recurse -Force` instead of `rm -rf`.
- Use `Copy-Item` not `cp`.
- Use `Set-Location` or `cd`, both work.
- Path separators: prefer forward slashes in Python code (works on both), use backslashes only in `.ps1` scripts.
- Activate venv with `.\.venv\Scripts\Activate.ps1`.

## Healthcare safety rules (non-negotiable)

1. **Synthetic data only.** Never write code that loads real patient data. If asked, refuse and explain HIPAA risk.
2. **Cite every clinical assertion.** Every LLM output about a patient must include FHIR resource references like `Observation/abc123`. If the model generates a clinical claim without a citation, the code must reject it.
3. **Clinician in the loop.** Agents draft, clinicians decide. Never write a tool that auto-submits to a real payer or external system without an explicit human confirmation step.
4. **Stay out of FDA SaMD.** This is decision support and patient communication, not diagnosis or treatment recommendation. The four 21st Century Cures Act non-device CDS criteria must be satisfied: (a) does not analyze image, signal, or IVD data; (b) displays medical information; (c) supports the HCP recommendation; (d) the HCP can independently review the basis of the recommendation. If you find yourself building something that violates these, stop and flag it.
5. **No autonomous risk predictions.** When the Risk Agent computes preeclampsia risk, it cites ACOG-published rules. It does not invent its own risk model.
6. **No prescribing.** Agents never tell a patient or clinician to take a specific medication dose without grounding in an existing MedicationRequest or a published guideline.
7. **PHI in logs.** Never log a full FHIR resource body. Log resource ID, type, and SHARP trace ID only.

## SHARP context propagation

SHARP = Prompt Opinion's healthcare context propagation spec. Until we have the official spec confirmed, we use these HTTP headers:

- `X-SHARP-Patient-Id`: FHIR Patient resource ID for the active patient
- `X-SHARP-FHIR-Server-URL`: base URL of the FHIR server
- `X-SHARP-FHIR-Access-Token`: bearer token for FHIR access
- `X-SHARP-Encounter-Id`: optional, current Encounter
- `X-SHARP-User-Role`: clinician | patient | care-coordinator
- `X-SHARP-Trace-Id`: UUID for end-to-end audit
- `X-SHARP-Locale`: BCP-47 language tag for patient communication (e.g. `es-US`, `en-US`)

Every MCP tool must accept these. Every A2A agent must propagate them on outbound calls. Use `mcp_server/src/sharp/context.py` as the single source of truth.

When the Prompt Opinion SHARP spec is published or shared, swap our header names for theirs in one place: `sharp/context.py`.

## How A2A agents call MCP tools

Always go through `a2a_agents._base.call_mcp_tool`. It uses `fastmcp.Client` over `StreamableHttpTransport` and propagates SHARP context two ways:

- as HTTP-level headers on the transport (so any future SHARP-aware middleware sees them);
- as a `headers` dict in the tool arguments (the MCP tools in `server.py` parse `SharpContext` from this dict via `_ctx_from_request_headers`).

Every MCP tool must declare `headers: dict[str, str] | None = None` in its signature, even if it ignores the value (see `healthcheck`). This keeps the call signature uniform so agents never have to branch.

Do not POST to `/tools/<name>`. FastMCP's streamable-http transport does not serve those URLs; calls will fail. The MCP endpoint is `${MCP_BASE_URL}/mcp`.

## Orchestrator sub-agent URLs

`a2a_agents/orchestrator/agent.py` builds `SUB_AGENT_URLS` from env vars with localhost fallbacks:

| Env var | Local default | Cloud Run value (set by deploy) |
|---|---|---|
| `RISK_AGENT_URL` | `http://localhost:8002/invoke` | Cloud Run URL + `/invoke` |
| `COVERAGE_AGENT_URL` | `http://localhost:8003/invoke` | Cloud Run URL + `/invoke` |
| `EDUCATION_AGENT_URL` | `http://localhost:8004/invoke` | Cloud Run URL + `/invoke` |
| `POSTPARTUM_WATCH_URL` | `http://localhost:8005/invoke` | Cloud Run URL + `/invoke` |

`deploy.ps1` sets these automatically via `gcloud run services update` after first deploy. Never hardcode localhost URLs on Cloud Run.

## Deploy pipeline (infrastructure/deploy.ps1)

`deploy.ps1` is idempotent and handles all prereqs before submitting the build:

1. Creates Artifact Registry repo `maternasquad` in `europe-west4` if it does not exist.
2. Creates Secret Manager secret `ANTHROPIC_API_KEY` (reads from `.env`) if it does not exist.
3. Grants `roles/secretmanager.secretAccessor` to Cloud Build SA and Compute SA.
4. Grants `roles/run.admin` and `roles/iam.serviceAccountUser` to Cloud Build SA.
5. Submits `infrastructure/cloudbuild.yaml`.

Cloud Build pipeline order:
- HAPI mirror + Python image builds run in parallel.
- HAPI deployed first (no Python images needed).
- Synthea bundles loaded into HAPI via `curl` from Cloud Build.
- MCP + 5 agents deployed after images are pushed and HAPI is loaded.
- Orchestrator updated last with real sub-agent URLs.

## Code quality rules

- Type hints everywhere. Use Pydantic v2 for any structured data crossing a boundary.
- One Pydantic model per FHIR resource we read. Do not pass raw dicts around.
- Async by default for I/O. Use `httpx.AsyncClient` for FHIR calls.
- No `print()` in production code. Use `structlog` configured to JSON output.
- Tests with pytest. Every MCP tool needs at least one happy-path test against the local HAPI server.
- Docstrings: Google style. Public functions explain WHAT and WHY, not HOW.
- Linting: `ruff` for fast lint, `mypy --strict` for types.

## Prompt engineering rules

- All prompts live in `*/prompts/*.md` files, not inline strings. Load them at startup.
- MCP tool prompts live in `mcp_server/prompts/`. Load them via `from mcp_server.src.prompts import load as load_prompt; SYSTEM_PROMPT_X = load_prompt("name")` (no `.md` suffix). The loader strips YAML frontmatter and is `lru_cache`'d.
- Agent prompts live in `a2a_agents/<agent>/prompts/system.md`. Load via `a2a_agents._base.load_prompt(AGENT_DIR)`.
- Every prompt has a YAML frontmatter with `name`, `purpose`, `model`, `temperature`, `max_output_tokens`, `version`.
- System prompts must include: role, hard constraints, output schema, citation requirement, refusal cases.
- For structured outputs, use Claude tool use via `generate_structured()`. The function converts the Pydantic schema to a JSON schema tool and forces `tool_choice` to that tool. Validate with `schema.model_validate(block.input)`.
- For narratives, force citations as `[Observation/abc123]` inline tokens, post-validate them via `mcp_server/src/gemini.py:CITATION_PATTERN`.

## Current state (2026-05-10 night)

All 7 services deployed and verified responding on Cloud Run. Smoke tested end-to-end with 3 Synthea personas. The clinician_summary citation guard works (fixed via prompt engineering on 2026-05-09 + max_output_tokens bumped to 1500 on 2026-05-10).

**Cloud Run URLs (region europe-west4, project maternasquad):**

- HAPI:             https://maternasquad-hapi-mdf575wm2q-ez.a.run.app
- MCP:              https://maternasquad-mcp-mdf575wm2q-ez.a.run.app
- Orchestrator:     https://maternasquad-orchestrator-mdf575wm2q-ez.a.run.app
- Risk:             https://maternasquad-risk-agent-mdf575wm2q-ez.a.run.app
- Coverage:         https://maternasquad-coverage-agent-mdf575wm2q-ez.a.run.app
- Education:        https://maternasquad-education-agent-mdf575wm2q-ez.a.run.app
- Postpartum watch: https://maternasquad-postpartum-watch-mdf575wm2q-ez.a.run.app

**Patients on Cloud Run HAPI** (different IDs from local):
- Patient/1076: Cordelia (preeclampsia demo star, Detroit)
- Patient/1569: Cyndi (postpartum mental health, rural KY)
- Patient/2218: Yuri (GDM, Houston, Spanish locale)

**Prompt Opinion registration status:**
- ✅ MCP Server registered ("MaternaSquad MCP - Maternal Clinical Toolbox") in Configuration → MCP Servers
- ✅ 5 External Agents registered in Agents → External Agents (Orchestrator, Risk, Coverage, Education, Postpartum Watch)
- ⚠️ Po-native "MaternaSquad Care Coordinator" orchestrator: Basic tab filled but blocked. The Linked Agents tab requires Po-native Custom Agents (not our External Agents). Save kept failing. Pause and revisit via the Tools tab approach.

**Where to resume 2026-05-11:**
1. Configure the Po Care Coordinator's `Tools` tab to attach the MaternaSquad MCP, then write a System Prompt, save. OR pivot to activating the General Chat Agent with our MCP tools.
2. Live test the chat inside Prompt Opinion with Patient/1076.
3. Publish to Marketplace Studio (requires paid subscription per UI warning - check if free tier can publish).
4. Write README.md.
5. Register on Devpost (agents-assemble.devpost.com).
6. Record demo video under 3:00 (script at docs/DEMO_SCRIPT.md, marketplace copy at docs/MARKETPLACE_LISTINGS.md).
7. Submit before 2026-05-11 23:00 EDT.

**Important after every full deploy:** the make-public Cloud Build step always fails (compute SA lacks setIamPolicy). Run this PowerShell loop locally to re-grant `allUsers/run.invoker`:

```powershell
foreach ($svc in @("maternasquad-hapi","maternasquad-mcp","maternasquad-orchestrator","maternasquad-risk-agent","maternasquad-coverage-agent","maternasquad-education-agent","maternasquad-postpartum-watch")) {
    gcloud run services add-iam-policy-binding $svc --region=europe-west4 --project=maternasquad --member="allUsers" --role="roles/run.invoker" --quiet | Out-Null
}
```

## Writing style for the user

- The user is a Spanish speaker actively learning English. They asked for grammar corrections in chat, not in code or comments.
- Be concise. Lead with the answer.
- No em dashes ever in any output to the user (chat or generated docs). Use commas, periods, parentheses, or "to" for ranges.
- For code comments, use plain English at intermediate level. Avoid idioms.
- For commit messages, use conventional commits in lowercase: `feat: ...`, `fix: ...`, `docs: ...`.

## When the user asks "build X"

1. Restate the goal in one sentence.
2. List the files you will create or change.
3. Flag any healthcare safety concerns first.
4. Then write the code.
5. End with the PowerShell command to run or test what you built.

## When you are stuck or uncertain

- Do not guess at FHIR field names. Open `https://hl7.org/fhir/R4/` style docs or `web_search` for the current FHIR R4 resource definition.
- Do not invent ACOG rules. Cite the ACOG Practice Bulletin number and year.
- Do not guess at SHARP spec details. Ask the user, then check `https://promptopinion.ai` or the hackathon resources page.
- For Da Vinci PA references, the canonical IG is `https://hl7.org/fhir/us/davinci-pas/`.

## Hackathon-specific priorities

- Demo video is under 3 minutes. Every feature must contribute to a demo moment or it is cut.
- The demo must run inside the Prompt Opinion platform, not a custom UI.
- Marketplace footprint matters: register each agent and the MCP server as separate listings if the platform allows.
- Judges include Josh Mandel (FHIR), Alice Zheng (women's health VC), Stephon Proctor (CHOP), Piyush Mathur (ICU), Joshua Hickey (Mayo), Parth Tripathi (Vertex AI Gemini). Match the depth and rigor they will expect.
- Submit on Devpost: agents-assemble.devpost.com

## Files of note

- `mcp_server/src/server.py`: registers all 8 MCP tools plus `healthcheck` against FastMCP.
- `mcp_server/src/sharp/context.py`: single source of truth for SHARP header names and `SharpContext`.
- `mcp_server/src/gemini.py`: Anthropic Claude wrapper (filename kept for import compatibility). Exposes `generate_text`, `generate_structured`, and `CITATION_PATTERN`. Uses `claude-sonnet-4-6` by default with adaptive thinking.
- `mcp_server/src/prompts.py`: loader for `mcp_server/prompts/*.md`. Use it for every MCP tool system prompt.
- `mcp_server/src/audit.py`: JSON-line audit writer. Never logs PHI bodies.
- `a2a_agents/_base.py`: shared FastAPI scaffolding plus `call_mcp_tool` (the only correct way to reach the MCP server).
- `a2a_agents/orchestrator/agent.py`: reads sub-agent URLs from env vars (`RISK_AGENT_URL` etc.) with localhost fallbacks.
- `a2a_agents/orchestrator/routing.py`: pure `plan_for` keyword router. Keep this LLM-free so the unit test stays fast.
- `infrastructure/deploy.ps1`: one-shot deploy script (creates repo, secret, IAM, then builds).
- `infrastructure/cloudbuild.yaml`: Cloud Build pipeline (HAPI + 6 Python services, no Gemini references).
- `mcp_server/tests/`, `a2a_agents/tests/`: pytest suites. All 15 tests must stay green.

## Files you should never edit without confirmation

- `pyproject.toml` (dependency drift breaks deploy)
- `infrastructure/cloudbuild.yaml` (CI pipeline)
- `.env` (user secrets)
- Anything under `synthea/output/` (generated, regenerable)

## Quick command reference (Windows PowerShell)

```powershell
# Activate venv (already created; do not recreate)
.\.venv\Scripts\Activate.ps1

# Bring up the local stack (in this order)
.\scripts\start_hapi.ps1                       # needs Docker Desktop running
.\synthea\load_to_hapi.ps1                     # personas.json already exists

# Run MCP server (terminal A)
.\scripts\run_mcp.ps1                          # serves http://localhost:8080/mcp

# Run all A2A agents (spawns 5 PS windows)
.\scripts\run_agents.ps1

# End-to-end smoke against a known patient ID
.\scripts\smoke_test.ps1 2047                  # Cordelia (preeclampsia demo star)
.\scripts\smoke_test.ps1 3189                  # Yuri / GDM / Spanish
.\scripts\smoke_test.ps1 2540                  # Cyndi / rural / mental health

# Run tests
pytest -v                                       # 15 tests should pass

# Type check
mypy --strict mcp_server/src a2a_agents

# Lint
ruff check .

# Deploy to Cloud Run (handles all prereqs automatically)
.\infrastructure\deploy.ps1

# Inspect the audit trail
Get-Content .\audit\maternasquad.log | Select-Object -Last 20

# Check Cloud Run service logs
gcloud run services logs read maternasquad-mcp --region=europe-west4 --limit=50
gcloud run services logs read maternasquad-orchestrator --region=europe-west4 --limit=50
```

## End

Stay focused on the demo path. Cut anything that does not serve the 3-minute video.
