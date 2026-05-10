# Start a local HAPI FHIR R4 server in Docker.
# Exposed on http://localhost:8090/fhir

$ErrorActionPreference = "Stop"

Write-Host "Starting HAPI FHIR R4 server on http://localhost:8090/fhir" -ForegroundColor Cyan

$existing = docker ps -a --filter "name=hapi-fhir-maternasquad" --format "{{.Names}}"
if ($existing -eq "hapi-fhir-maternasquad") {
    Write-Host "Container exists. Restarting..." -ForegroundColor Yellow
    docker start hapi-fhir-maternasquad | Out-Null
} else {
    docker run -d `
        --name hapi-fhir-maternasquad `
        -p 8090:8080 `
        -e hapi.fhir.fhir_version=R4 `
        -e hapi.fhir.allow_external_references=true `
        -e hapi.fhir.cors.allowed_origin=* `
        hapiproject/hapi:latest | Out-Null
}

Write-Host "Waiting for HAPI to be ready..." -NoNewline
$maxWait = 60
for ($i = 0; $i -lt $maxWait; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8090/fhir/metadata" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            Write-Host " ready" -ForegroundColor Green
            break
        }
    } catch { Write-Host "." -NoNewline }
}

Write-Host "HAPI FHIR R4 ready at http://localhost:8090/fhir" -ForegroundColor Green
