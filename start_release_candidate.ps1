param(
    [string]$BindAddress = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment Python tidak ditemukan."
}

Set-Location $Root

& $Python ".\release_tool.py" preflight --strict

if ($LASTEXITCODE -ne 0) {
    throw "Production preflight gagal."
}

Write-Host ""
Write-Host "Menjalankan DocuRapi 5.0.0-rc1..." -ForegroundColor Green
Write-Host "Alamat: http://$BindAddress`:$Port"
Write-Host ""

& $Python `
    -m uvicorn `
    app:app `
    --host $BindAddress `
    --port $Port `
    --workers 1
