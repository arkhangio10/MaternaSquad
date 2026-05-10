# End-to-end smoke test against the local stack.
# Assumes HAPI is up, MCP server running on 8080, agents running on 8001-8005,
# and at least one Synthea patient is loaded with a known ID.

$ErrorActionPreference = "Stop"

$patientId = if ($args.Count -ge 1) { $args[0] } else { "example-patient" }
$fhirUrl = "http://localhost:8090/fhir"

$headers = @{
    "X-SHARP-Patient-Id"       = $patientId
    "X-SHARP-FHIR-Server-URL"  = $fhirUrl
    "X-SHARP-User-Role"        = "clinician"
    "X-SHARP-Locale"           = "en-US"
    "X-SHARP-Trace-Id"         = [guid]::NewGuid().ToString()
    "Content-Type"             = "application/json"
}

Write-Host "[1/3] Healthcheck on MCP server"
# FastMCP streamable-http only serves /mcp. A GET returns 406 (not 404),
# which proves the server is listening. Plain HTTP /healthcheck does not exist.
try {
    Invoke-WebRequest -Uri "http://localhost:8080/mcp" -Method GET -UseBasicParsing -ErrorAction Stop | Out-Null
    Write-Host "  MCP server UP" -ForegroundColor Green
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 406 -or $code -eq 405) {
        Write-Host "  MCP server UP (responded $code to GET /mcp)" -ForegroundColor Green
    } else {
        throw "MCP server not reachable at http://localhost:8080/mcp (status $code)"
    }
}

Write-Host ""
Write-Host "[2/3] Healthcheck on Orchestrator"
$orch = Invoke-RestMethod -Uri "http://localhost:8001/healthcheck" -Method GET
$orch | ConvertTo-Json -Depth 5

Write-Host ""
Write-Host "[3/3] End-to-end Orchestrator invoke"
$body = @{
    user_message = "Set up Aisha for the third trimester. She has been complaining about headaches."
    context = @{}
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8001/invoke" -Method POST -Headers $headers -Body $body
Write-Host ""
$response | ConvertTo-Json -Depth 10
