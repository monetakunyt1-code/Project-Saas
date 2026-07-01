param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "preflight",
        "acceptance",
        "build",
        "start"
    )]
    [string]$Action
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment Python tidak ditemukan."
}

Set-Location $Root

switch ($Action) {
    "preflight" {
        & $Python ".\release_tool.py" preflight --strict
    }

    "acceptance" {
        & $Python ".\acceptance_cli.py" run --mode full
    }

    "build" {
        & $Python ".\release_tool.py" build
    }

    "start" {
        & "$Root\start_release_candidate.ps1"
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "Perintah release gagal: $Action"
}
