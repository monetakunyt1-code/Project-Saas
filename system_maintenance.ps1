param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "backup",
        "list",
        "verify",
        "restore",
        "prune",
        "health"
    )]
    [string]$Action,

    [string]$BackupId = "",

    [string]$Label = "manual_cli",

    [int]$Keep = 14,

    [switch]$Apply,

    [switch]$Force
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment Python tidak ditemukan."
}

Set-Location $Root

$Arguments = @(
    "system_maintenance.py",
    $Action
)

if ($Action -eq "backup") {
    $Arguments += @(
        "--label",
        $Label
    )
}

if (
    $Action -eq "verify"
    -or $Action -eq "restore"
) {
    if ([string]::IsNullOrWhiteSpace($BackupId)) {
        throw "BackupId wajib diisi."
    }

    $Arguments += @(
        "--backup-id",
        $BackupId
    )
}

if ($Action -eq "restore") {
    if ($Apply) {
        $Arguments += "--apply"
    }

    if ($Force) {
        $Arguments += "--force"
    }
}

if ($Action -eq "prune") {
    $Arguments += @(
        "--keep",
        $Keep
    )
}

& $Python @Arguments