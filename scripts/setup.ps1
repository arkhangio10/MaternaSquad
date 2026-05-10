# One-time setup. Run from the project root.

$ErrorActionPreference = "Stop"

Write-Host "MaternaSquad bootstrap" -ForegroundColor Cyan
Write-Host "======================" -ForegroundColor Cyan

# 1. Python venv
if (-not (Test-Path ".venv")) {
    Write-Host "[1/5] Creating Python venv (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "[1/5] Venv already exists, skipping." -ForegroundColor Gray
}

# 2. Activate
Write-Host "[2/5] Activating venv..." -ForegroundColor Yellow
.\.venv\Scripts\Activate.ps1

# 3. Install deps
Write-Host "[3/5] Installing Python dependencies (this takes a couple minutes)..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -e ".[dev]"

# 4. .env
if (-not (Test-Path ".env")) {
    Write-Host "[4/5] Creating .env from .env.example. Open it and fill in GCP_PROJECT_ID." -ForegroundColor Yellow
    Copy-Item .env.example .env
    notepad .env
} else {
    Write-Host "[4/5] .env exists, skipping." -ForegroundColor Gray
}

# 5. Audit folder
New-Item -ItemType Directory -Force -Path audit | Out-Null

Write-Host "[5/5] Done." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. .\scripts\start_hapi.ps1                # start local HAPI FHIR R4"
Write-Host "  2. .\synthea\generate_personas.ps1         # generate the 3 demo patients"
Write-Host "  3. .\synthea\load_to_hapi.ps1              # post bundles to HAPI"
Write-Host "  4. gcloud auth application-default login   # for Vertex AI Gemini"
Write-Host "  5. .\scripts\run_mcp.ps1                   # in terminal A"
Write-Host "  6. .\scripts\run_agents.ps1                # spawns 5 agents"
Write-Host "  7. .\scripts\smoke_test.ps1 <patient-id>   # end-to-end test"
