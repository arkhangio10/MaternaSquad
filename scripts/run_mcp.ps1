# Run the MaternaSquad MCP server locally.

$ErrorActionPreference = "Stop"

# Activate venv if not active
if (-not $env:VIRTUAL_ENV) {
    .\.venv\Scripts\Activate.ps1
}

# Load .env
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

Write-Host "Starting maternasquad-mcp on port $($env:MCP_SERVER_PORT)" -ForegroundColor Cyan
python -m mcp_server.src.server
