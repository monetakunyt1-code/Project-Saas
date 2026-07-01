$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment belum tersedia."
}

$Existing = Get-NetTCPConnection `
    -LocalPort 8000 `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($Existing) {
    Write-Host "DocuRapi sudah berjalan di port 8000." -ForegroundColor Yellow
    Start-Process "http://127.0.0.1:8000"
    exit
}

$Command = "Set-Location '$Root'; & '$Python' -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload"

Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-ExecutionPolicy", `
    "Bypass", `
    "-Command", `
    $Command

Start-Sleep -Seconds 4
Start-Process "http://127.0.0.1:8000"

Write-Host "DocuRapi berjalan di http://127.0.0.1:8000" -ForegroundColor Green