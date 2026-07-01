param(
    [ValidateSet(
        "health",
        "self-test",
        "cleanup",
        "reservations"
    )]
    [string]$Action = "health"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment Python tidak ditemukan."
}

Set-Location $Root

switch ($Action) {
    "health" {
        & $Python `
            ".\billing_enforcement_cli.py" `
            health
    }

    "self-test" {
        & $Python `
            ".\billing_enforcement_cli.py" `
            self-test
    }

    "cleanup" {
        & $Python `
            ".\billing_enforcement_cli.py" `
            cleanup
    }

    "reservations" {
        & $Python `
            ".\billing_enforcement_cli.py" `
            reservations
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "Perintah Billing Enforcement gagal: $Action"
}
