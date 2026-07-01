param(
    [ValidateSet("check", "start", "status", "stop", "logs")]
    [string]$Action = "check"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$InfraDirectory = Join-Path $Root "infra"
$EnvironmentFile = Join-Path $InfraDirectory ".env"
$ComposeFile = Join-Path $InfraDirectory "docker-compose.infrastructure.yml"

if (-not (Test-Path $EnvironmentFile)) {
    throw "File infra\.env tidak ditemukan."
}

if (-not (Test-Path $ComposeFile)) {
    throw "Docker Compose infrastructure tidak ditemukan."
}

$DockerCommand = Get-Command docker -ErrorAction SilentlyContinue

switch ($Action) {
    "check" {
        Write-Host ""
        Write-Host "PEMERIKSAAN INFRASTRUKTUR DOCURAPI" -ForegroundColor Cyan
        Write-Host "Environment : $EnvironmentFile"
        Write-Host "Compose     : $ComposeFile"

        if ($null -eq $DockerCommand) {
            Write-Host "Docker      : BELUM TERPASANG" -ForegroundColor Yellow
            return
        }

        docker info *> $null

        if ($LASTEXITCODE -ne 0) {
            Write-Host "Docker      : DESKTOP BELUM AKTIF" -ForegroundColor Yellow
            return
        }

        Write-Host "Docker      : AKTIF" -ForegroundColor Green

        foreach ($Port in 5432, 6379, 9000, 9001) {
            $PortActive = Test-NetConnection -ComputerName "127.0.0.1" -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue

            if ($PortActive) {
                Write-Host "Port $Port   : AKTIF" -ForegroundColor Green
            }
            else {
                Write-Host "Port $Port   : BELUM AKTIF" -ForegroundColor Yellow
            }
        }
    }

    "start" {
        if ($null -eq $DockerCommand) {
            throw "Docker belum terpasang."
        }

        docker info *> $null

        if ($LASTEXITCODE -ne 0) {
            throw "Docker Desktop belum aktif."
        }

        docker compose --env-file $EnvironmentFile -f $ComposeFile up -d

        if ($LASTEXITCODE -ne 0) {
            throw "Container infrastruktur gagal dijalankan."
        }

        docker compose --env-file $EnvironmentFile -f $ComposeFile ps
    }

    "status" {
        docker compose --env-file $EnvironmentFile -f $ComposeFile ps
    }

    "stop" {
        docker compose --env-file $EnvironmentFile -f $ComposeFile down
    }

    "logs" {
        docker compose --env-file $EnvironmentFile -f $ComposeFile logs --tail 100
    }
}
