$Connections = Get-NetTCPConnection `
    -LocalPort 8000 `
    -State Listen `
    -ErrorAction SilentlyContinue

foreach ($Connection in $Connections) {
    Stop-Process `
        -Id $Connection.OwningProcess `
        -Force `
        -ErrorAction SilentlyContinue
}

Write-Host "Server DocuRapi dihentikan." -ForegroundColor Yellow