param(
    [ValidateSet(
        "structural",
        "full"
    )]
    [string]$Mode = "full",

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment Python tidak ditemukan."
}

Set-Location $Root

$Arguments = @(
    "acceptance_cli.py",
    "run",
    "--mode",
    $Mode
)

if ($Json) {
    $Arguments += "--json"
}

& $Python @Arguments
