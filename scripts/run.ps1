# PowerShell script para inicializar todos os servicos do Atlas Urbano no Windows
param (
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

function Test-PortOpen([string]$HostName, [int]$Port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect($HostName, $Port)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       Atlas Urbano de Paulo Afonso - Inicializacao       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Banco de Dados MariaDB
Write-Host "`n==> [1/4] Banco de dados (MariaDB em :3306)..." -ForegroundColor Yellow
powershell -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "db.ps1") start

# 2. Verificacao / Carga de dados
Write-Host "`n==> [2/4] Verificando dados no banco de dados..." -ForegroundColor Yellow
$PythonExe = Join-Path $RootDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "Ambiente virtual nao encontrado. Criando .venv..."
    python -m venv .venv
    & (Join-Path $RootDir ".venv\Scripts\pip.exe") install -r (Join-Path $RootDir "backend\requirements.txt")
}

$hasData = $false
try {
    $checkCmd = "import pymysql; conn = pymysql.connect(host='127.0.0.1', port=3306, user='atlas', password='atlas', database='atlas_urbano'); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM buildings'); print(cur.fetchone()[0]); conn.close()"
    $count = & $PythonExe -c $checkCmd 2>$null
    if ($count -and [int]$count -gt 0) {
        Write-Host "  Banco ja possui $count registros na tabela 'buildings'." -ForegroundColor Green
        $hasData = $true
    }
} catch {
    $hasData = $false
}

if (-not $hasData) {
    Write-Host "  Tabela 'buildings' vazia ou inexistente. Executando import_data.py..." -ForegroundColor Yellow
    & $PythonExe (Join-Path $RootDir "import_data.py")
}

# 3. Backend FastAPI
Write-Host "`n==> [3/4] Backend (FastAPI em http://127.0.0.1:8000)..." -ForegroundColor Yellow
if (Test-PortOpen "127.0.0.1" 8000) {
    Write-Host "  Backend ja esta rodando na porta 8000." -ForegroundColor Green
} else {
    Write-Host "  Iniciando backend..."
    $backendOutLog = Join-Path $RootDir "backend.log"
    $backendErrLog = Join-Path $RootDir "backend_err.log"
    Start-Process -FilePath $PythonExe -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $RootDir -WindowStyle Hidden -RedirectStandardOutput $backendOutLog -RedirectStandardError $backendErrLog

    $backendOk = $false
    for ($i = 1; $i -le 15; $i++) {
        Start-Sleep -Seconds 1
        if (Test-PortOpen "127.0.0.1" 8000) {
            $backendOk = $true
            break
        }
    }
    if ($backendOk) {
        Write-Host "  Backend FastAPI iniciado com sucesso!" -ForegroundColor Green
    } else {
        Write-Error "ERRO: Backend nao subiu na porta 8000. Verifique $backendErrLog"
    }
}

# 4. Frontend Vite
Write-Host "`n==> [4/4] Frontend (Vite em http://127.0.0.1:5173)..." -ForegroundColor Yellow
$frontendDir = Join-Path $RootDir "frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "  Instalando dependencias do frontend (npm install)..."
    Push-Location $frontendDir
    npm install
    Pop-Location
}

if (Test-PortOpen "127.0.0.1" 5173) {
    Write-Host "  Frontend ja esta rodando em http://127.0.0.1:5173/" -ForegroundColor Green
} else {
    Write-Host "  Iniciando servidor de desenvolvimento do Vite..."
    $frontendOutLog = Join-Path $RootDir "frontend.log"
    $frontendErrLog = Join-Path $RootDir "frontend_err.log"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev -- --port 5173 --host 127.0.0.1" -WorkingDirectory $frontendDir -WindowStyle Hidden -RedirectStandardOutput $frontendOutLog -RedirectStandardError $frontendErrLog

    $frontendOk = $false
    for ($i = 1; $i -le 15; $i++) {
        Start-Sleep -Seconds 1
        if (Test-PortOpen "127.0.0.1" 5173) {
            $frontendOk = $true
            break
        }
    }
    if ($frontendOk) {
        Write-Host "  Frontend Vite iniciado com sucesso!" -ForegroundColor Green
    } else {
        Write-Error "ERRO: Frontend nao subiu na porta 5173. Verifique $frontendLog"
    }
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "   PROJETO PRONTO PARA APRESENTACAO NO LOCALHOST!         " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Frontend:  http://127.0.0.1:5173/" -ForegroundColor Cyan
Write-Host "  Backend:   http://127.0.0.1:8000/" -ForegroundColor Cyan
Write-Host "  API Docs:  http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:5173/"
}
