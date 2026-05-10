# MaternaSquad

> The Avengers of Maternal Care. A multi-agent A2A system for high-risk pregnancy through 12 weeks postpartum, with a shared MCP tool server.

Built for the Agents Assemble Healthcare AI Endgame Challenge (Prompt Opinion, deadline May 11, 2026).

## What this is

Five specialist A2A agents that assemble around one mother, plus a shared MCP server with reusable tools. All agents propagate SHARP healthcare context across hops and operate on FHIR R4 data.

The five agents:

1. **Orchestrator** — clinician-facing entry point, routes to the squad.
2. **Risk Agent** — preeclampsia, GDM, preterm risk stratification with ACOG citations.
3. **Coverage Agent** — prior auth and benefits navigation for maternal services.
4. **Education Agent** — patient-facing teach-back at controlled reading level, multilingual.
5. **Postpartum Watch Agent** — 12-week danger window symptom triage and escalation.

The shared MCP server `maternasquad-mcp` exposes 8 to 10 tools the agents call.

## Stack

- Python 3.11
- Gemini 2.5 Flash (Vertex AI) for reasoning and generation
- FastMCP 2.x for the MCP server
- A2A agents over FastAPI with the Google ADK agent contract (SHARP headers in, JSON out). Drop-in ADK adoption is planned post-hackathon; the wrapper in `a2a_agents/_base.py` keeps the surface compatible.
- HAPI FHIR R4 server (Docker, local) loaded with Synthea synthetic patients
- Cloud Run for production deployment
- Synthea for synthetic patient generation

## Prerequisites (Windows + PowerShell)

```powershell
# Install Python 3.11
winget install Python.Python.3.11

# Install Docker Desktop
winget install Docker.DockerDesktop

# Install Google Cloud SDK
winget install Google.CloudSDK

# Install Java 17 (Synthea requirement)
winget install Microsoft.OpenJDK.17

# Install Git
winget install Git.Git

# Install VS Code
winget install Microsoft.VisualStudioCode

# Install Claude Code
npm install -g @anthropic-ai/claude-code
```

After installation, restart PowerShell and verify:

```powershell
python --version    # 3.11.x
docker --version
gcloud --version
java -version       # 17.x
claude --version
```

## Setup (one time)

```powershell
# 1. Clone or copy the project
cd C:\projects
# (place the maternasquad folder here)
cd maternasquad

# 2. Create Python virtual env
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Copy env template and fill in values
Copy-Item .env.example .env
notepad .env

# 5. Authenticate with Google Cloud (for Vertex AI Gemini access)
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_GCP_PROJECT_ID

# 6. Start local HAPI FHIR R4 server
.\scripts\start_hapi.ps1

# 7. Generate Synthea personas and load to HAPI
.\synthea\generate_personas.ps1
.\synthea\load_to_hapi.ps1
```

## Run locally

Open three PowerShell terminals.

```powershell
# Terminal 1: MCP server
.\scripts\run_mcp.ps1

# Terminal 2: All A2A agents
.\scripts\run_agents.ps1

# Terminal 3: Test client
.\scripts\smoke_test.ps1
```

## Deploy to Cloud Run

```powershell
.\infrastructure\deploy.ps1
```

## Project layout

```
maternasquad/
├── .claude/CLAUDE.md         # Claude Code rules for this project
├── .vscode/                  # VS Code workspace config
├── docs/                     # Architecture, demo script, hackathon notes
├── mcp_server/               # Shared MCP server with 10 tools
│   ├── src/
│   │   ├── server.py         # FastMCP entry point
│   │   ├── sharp/            # SHARP Extension Specs context
│   │   ├── fhir/             # FHIR R4 client
│   │   └── tools/            # 10 MCP tools
│   └── prompts/              # Reusable prompt fragments
├── a2a_agents/
│   ├── orchestrator/         # Entry agent, talks to clinician
│   ├── risk_agent/           # ACOG-grounded risk stratification
│   ├── coverage_agent/       # Prior auth and benefits
│   ├── education_agent/      # Multilingual teach-back
│   └── postpartum_watch/     # 12-week danger window triage
├── synthea/
│   ├── modules/              # Custom Synthea modules
│   ├── generate_personas.ps1 # Generate the 3 demo personas
│   └── load_to_hapi.ps1      # Post bundles to local HAPI
├── infrastructure/
│   ├── Dockerfile.mcp
│   ├── Dockerfile.agent
│   ├── cloudbuild.yaml
│   └── deploy.ps1
└── scripts/                  # Local dev scripts (PowerShell)
```

## Demo personas (Synthea)

1. **Aisha Williams**, 32, Black, BMI 31, history of preterm birth, current pregnancy with rising BP. The demo star.
2. **Sofia Ramirez**, 28, Hispanic, GDM, language preference Spanish.
3. **Jordan Bell**, 19, rural ZIP, anxiety + postpartum depression risk.

## Healthcare safety constraints

This is a hackathon prototype. Hard rules:

- Synthetic data only. Never load real PHI.
- All clinical assertions cite a FHIR resource ID.
- Clinician confirms before any action.
- Designed to satisfy the four 21st Century Cures Act non-device CDS criteria so it stays out of FDA SaMD territory.
- Audit trail logs every agent decision with model version and SHARP context.

## License

MIT for the hackathon. Re-license before any production use.
