param(
    [ValidateSet(
        "health",
        "catalog",
        "self-test",
        "orders"
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
        & $Python ".\billing_cli.py" health
    }

    "catalog" {
        & $Python ".\billing_cli.py" catalog
    }

    "self-test" {
        & $Python ".\billing_cli.py" self-test
    }

    "orders" {
        & $Python ".\billing_cli.py" orders
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "Perintah Billing gagal: $Action"
}
