# Load Synthea bundles into the local HAPI FHIR R4 server.
# Captures the assigned Patient IDs and writes them to synthea/personas.json
# so downstream scripts (smoke_test, demo) can address them by name.

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BundleDir   = Join-Path $ProjectRoot "synthea\output\fhir"
$FhirBase    = if ($env:FHIR_BASE_URL) { $env:FHIR_BASE_URL } else { "http://localhost:8090/fhir" }
$Manifest    = Join-Path $ProjectRoot "synthea\personas.json"

if (-not (Test-Path $BundleDir)) {
    throw "No Synthea output found. Run .\synthea\generate_personas.ps1 first."
}

# Health check HAPI
try {
    Invoke-WebRequest -Uri "$FhirBase/metadata" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop | Out-Null
} catch {
    throw "HAPI FHIR unreachable at $FhirBase. Run .\scripts\start_hapi.ps1 first."
}

$personas = @{}

function Send-FhirBundle($file) {
    $body = Get-Content -Raw -Path $file.FullName -Encoding UTF8
    Invoke-RestMethod `
        -Uri $FhirBase `
        -Method POST `
        -Body $body `
        -ContentType "application/fhir+json" `
        -TimeoutSec 120
}

# Pass 1: load reference resources so patient bundles can resolve conditional references
Write-Host "Pass 1: loading practitioners and hospitals..." -ForegroundColor Yellow
Get-ChildItem $BundleDir -Filter "*.json" | Where-Object {
    $_.Name -match "^(hospital|practitioner)Information"
} | ForEach-Object {
    Write-Host "  $($_.Name)" -ForegroundColor Gray
    Send-FhirBundle $_ | Out-Null
}

# Pass 2: load patient bundles and capture Patient IDs
Write-Host ""
Write-Host "Pass 2: loading patients..." -ForegroundColor Yellow
Get-ChildItem $BundleDir -Filter "*.json" | Where-Object {
    $_.Name -notmatch "^(hospital|practitioner)Information"
} | ForEach-Object {
    Write-Host ""
    Write-Host "Loading $($_.Name)..." -ForegroundColor Cyan

    $response = Send-FhirBundle $_

    $patientEntry = $response.entry | Where-Object {
        $_.response.location -match "^Patient/"
    } | Select-Object -First 1

    if ($patientEntry) {
        $patientId = ($patientEntry.response.location -split "/")[1]
        $personas[$_.BaseName] = $patientId
        Write-Host "  Patient/$patientId" -ForegroundColor Green
    } else {
        Write-Warning "  No Patient created from $($_.Name)"
    }
}

# Persist mapping of file basename to Patient ID
$personas | ConvertTo-Json | Set-Content -Path $Manifest -Encoding UTF8

Write-Host ""
Write-Host "Loaded patients (saved to synthea\personas.json):" -ForegroundColor Green
$personas.GetEnumerator() | ForEach-Object {
    Write-Host "  $($_.Key) -> Patient/$($_.Value)"
}

Write-Host ""
Write-Host "Test with: .\scripts\smoke_test.ps1 <patient-id>" -ForegroundColor Cyan
