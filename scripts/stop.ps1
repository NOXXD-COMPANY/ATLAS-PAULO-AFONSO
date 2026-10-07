# PowerShell script para parar os serviços do Atlas Urbano (Frontend, Backend e MariaDB)
$ErrorActionPreference = "SilentlyContinue"

Write-Host "==> Parando Frontend (Vite/Node na porta 5173)..."
$viteConns = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $viteConns) {
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
}

Write-Host "==> Parando Backend (Uvicorn/Python na porta 8000)..."
$fastapiConns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $fastapiConns) {
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
}

Write-Host "==> Parando MariaDB (porta 3306)..."
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
powershell -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "db.ps1") stop

Write-Host "Todos os serviços foram parados com sucesso."
