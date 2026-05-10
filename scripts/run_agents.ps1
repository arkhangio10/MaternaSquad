# Run all 5 A2A agents in parallel PowerShell windows.

$ErrorActionPreference = "Stop"

$agents = @(
    @{ name = "orchestrator";          module = "a2a_agents.orchestrator.agent" },
    @{ name = "risk_agent";            module = "a2a_agents.risk_agent.agent" },
    @{ name = "coverage_agent";        module = "a2a_agents.coverage_agent.agent" },
    @{ name = "education_agent";       module = "a2a_agents.education_agent.agent" },
    @{ name = "postpartum_watch";      module = "a2a_agents.postpartum_watch.agent" }
)

foreach ($agent in $agents) {
    $cmd = ".\.venv\Scripts\Activate.ps1; python -m $($agent.module)"
    Write-Host "Starting $($agent.name)..." -ForegroundColor Cyan
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", $cmd
    Start-Sleep -Milliseconds 500
}

Write-Host "All agents launched. Check the new PowerShell windows." -ForegroundColor Green
Write-Host "  Orchestrator:        http://localhost:8001/healthcheck"
Write-Host "  Risk Agent:          http://localhost:8002/healthcheck"
Write-Host "  Coverage Agent:      http://localhost:8003/healthcheck"
Write-Host "  Education Agent:     http://localhost:8004/healthcheck"
Write-Host "  Postpartum Watch:    http://localhost:8005/healthcheck"
