param(
    [ValidateSet(
        "audit",
        "summary",
        "open",
        "paths"
    )]
    [string]$Action = "audit"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Report = Join-Path $Root "storage\readiness\latest_report.html"

if (-not (Test-Path $Python)) {
    throw "Virtual environment Python tidak ditemukan."
}

Set-Location $Root

switch ($Action) {
    "audit" {
        & $Python ".\saas_readiness_cli.py" audit

        if ($LASTEXITCODE -ne 0) {
            throw "SaaS Readiness Audit gagal."
        }
    }

    "summary" {
        & $Python ".\saas_readiness_cli.py" summary
    }

    "paths" {
        & $Python ".\saas_readiness_cli.py" paths
    }

    "open" {
        if (-not (Test-Path $Report)) {
            & $Python ".\saas_readiness_cli.py" audit

            if ($LASTEXITCODE -ne 0) {
                throw "SaaS Readiness Audit gagal."
            }
        }

        Start-Process $Report
    }
}
