[CmdletBinding()]
param(
    [switch]$Fast
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

Write-Host "Starting verification flow..."

Push-Location "$PSScriptRoot\.."
try {
    Write-Host "Bringing up PostgreSQL and Redis..."
    Invoke-Step { docker compose up -d postgres redis }

    Write-Host "Running backend migration + tests in container..."
    Invoke-Step { docker compose exec -T postgres psql -U postgres -d modelops -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;" }
    Invoke-Step { docker compose build backend }
    Invoke-Step { docker compose run --rm backend sh -lc "cd /app && alembic -c /app/alembic.ini upgrade head && PYTHONPATH=/app pytest -q" }

    if ($Fast) {
        Write-Host "Fast mode enabled: skipping frontend image build."
    }
    else {
        Write-Host "Building frontend in container..."
        Invoke-Step { docker compose build frontend }
    }

    Write-Host "Verification completed successfully."
}
finally {
    Write-Host "Stopping verification dependencies..."
    docker compose down
    Pop-Location
}
