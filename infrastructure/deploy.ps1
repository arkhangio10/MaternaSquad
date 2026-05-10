# Deploy MaternaSquad to Cloud Run via Cloud Build.
# Run from the maternasquad/ directory: .\infrastructure\deploy.ps1

$ErrorActionPreference = "Stop"

$ProjectId = if ($env:GCP_PROJECT_ID) { $env:GCP_PROJECT_ID } else {
    (gcloud config get-value project 2>$null).Trim()
}
$Region = if ($env:GCP_REGION) { $env:GCP_REGION } else { "europe-west4" }
$Repo   = "maternasquad"

if (-not $ProjectId) {
    throw "GCP_PROJECT_ID not set. Run: gcloud config set project <id>"
}

Write-Host "Project: $ProjectId  Region: $Region" -ForegroundColor Cyan

# ── 1. Artifact Registry repo ───────────────────────────────────────────────
Write-Host "Checking Artifact Registry repo..." -ForegroundColor Yellow
$repoExists = $false
try {
    gcloud artifacts repositories describe $Repo `
        --location=$Region --project=$ProjectId *>$null
    $repoExists = ($LASTEXITCODE -eq 0)
} catch { $repoExists = $false }

if (-not $repoExists) {
    Write-Host "  Creating repo $Repo in $Region..." -ForegroundColor Yellow
    gcloud artifacts repositories create $Repo `
        --repository-format=docker `
        --location=$Region `
        --project=$ProjectId
} else {
    Write-Host "  Repo already exists." -ForegroundColor Green
}

# ── 2. ANTHROPIC_API_KEY secret ─────────────────────────────────────────────
Write-Host "Checking Secret Manager secret..." -ForegroundColor Yellow
$secretExists = $false
try {
    gcloud secrets describe ANTHROPIC_API_KEY --project=$ProjectId *>$null
    $secretExists = ($LASTEXITCODE -eq 0)
} catch { $secretExists = $false }

if (-not $secretExists) {
    Write-Host "  Creating secret ANTHROPIC_API_KEY..." -ForegroundColor Yellow

    # Read key from env or .env file
    $apiKey = $env:ANTHROPIC_API_KEY
    if (-not $apiKey) {
        $envLine = Get-Content .env | Where-Object { $_ -match "^ANTHROPIC_API_KEY=" }
        $apiKey  = $envLine -replace "^ANTHROPIC_API_KEY=", ""
    }
    if (-not $apiKey) {
        throw "ANTHROPIC_API_KEY not found in environment or .env file"
    }

    $apiKey | gcloud secrets create ANTHROPIC_API_KEY `
        --data-file=- `
        --project=$ProjectId
} else {
    Write-Host "  Secret already exists." -ForegroundColor Green
}

# ── 3. IAM: Cloud Build → Secret Manager ────────────────────────────────────
Write-Host "Granting Secret Manager access to Cloud Build and Cloud Run..." -ForegroundColor Yellow
$projectNumber = (gcloud projects describe $ProjectId --format="value(projectNumber)").Trim()
$cbSA  = "$projectNumber@cloudbuild.gserviceaccount.com"
$crSA  = "$projectNumber-compute@developer.gserviceaccount.com"

foreach ($sa in @($cbSA, $crSA)) {
    gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY `
        --project=$ProjectId `
        --member="serviceAccount:$sa" `
        --role="roles/secretmanager.secretAccessor" | Out-Null
}
Write-Host "  Done." -ForegroundColor Green

# ── 4. IAM: Cloud Build → Cloud Run deployer ────────────────────────────────
Write-Host "Granting Cloud Run deploy roles to Cloud Build..." -ForegroundColor Yellow
foreach ($role in @("roles/run.admin", "roles/iam.serviceAccountUser")) {
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$cbSA" `
        --role=$role | Out-Null
}
Write-Host "  Done." -ForegroundColor Green

# ── 5. Configure Docker auth for Artifact Registry ──────────────────────────
Write-Host "Configuring Docker auth for Artifact Registry..." -ForegroundColor Yellow
gcloud auth configure-docker "$Region-docker.pkg.dev" --quiet

# ── 6. Submit Cloud Build ────────────────────────────────────────────────────
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "Submitting Cloud Build (~15 to 20 minutes)..." -ForegroundColor Yellow
gcloud builds submit `
    --config infrastructure/cloudbuild.yaml `
    --substitutions=_REGION=$Region,_REPO=$Repo `
    --project=$ProjectId `
    .

# ── 7. Print resulting URLs ──────────────────────────────────────────────────
Write-Host ""
Write-Host "Cloud Run services:" -ForegroundColor Green
$services = @(
    "maternasquad-hapi",
    "maternasquad-mcp",
    "maternasquad-orchestrator",
    "maternasquad-risk-agent",
    "maternasquad-coverage-agent",
    "maternasquad-education-agent",
    "maternasquad-postpartum-watch"
)
foreach ($svc in $services) {
    $url = (gcloud run services describe $svc `
        --region=$Region --project=$ProjectId `
        --format="value(status.url)" 2>$null).Trim()
    if ($url) {
        Write-Host "  $svc"
        Write-Host "    $url"
    }
}

Write-Host ""
Write-Host "Done. Register each URL on the Prompt Opinion Marketplace." -ForegroundColor Cyan
