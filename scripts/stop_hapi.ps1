# Stop and remove the local HAPI FHIR container.

$ErrorActionPreference = "SilentlyContinue"
docker stop hapi-fhir-maternasquad | Out-Null
docker rm hapi-fhir-maternasquad | Out-Null
Write-Host "Stopped HAPI FHIR." -ForegroundColor Green
