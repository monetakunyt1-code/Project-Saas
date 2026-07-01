
param(
    [ValidateSet(
        "health",
        "self-test",
        "configure-sandbox",
        "configure-production"
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
        & $Python ".\midtrans_cli.py" health
    }

    "self-test" {
        & $Python ".\midtrans_cli.py" self-test
    }

    "configure-sandbox" {
        & $Python ".\midtrans_cli.py" configure --environment sandbox
    }

    "configure-production" {
        & $Python ".\midtrans_cli.py" configure --environment production
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "Perintah Midtrans gagal: $Action"
}
