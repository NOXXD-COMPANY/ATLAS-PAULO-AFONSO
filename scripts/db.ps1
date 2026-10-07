# PowerShell script para gerenciar o MariaDB local do Atlas Urbano no Windows
param (
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$DataDir = Join-Path $RootDir ".mysql-data"
$MariaDir = "C:\Program Files\MariaDB 13.0\bin"
$MariaDbExe = Join-Path $MariaDir "mariadbd.exe"
$MariaAdminExe = Join-Path $MariaDir "mariadb-admin.exe"
$MariaCliExe = Join-Path $MariaDir "mariadb.exe"
$MariaInstallExe = Join-Path $MariaDir "mariadb-install-db.exe"
$ErrLog = Join-Path $DataDir "mysql.err"
$PidFile = Join-Path $DataDir "mysql.pid"

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

switch ($Action.ToLower()) {
    "start" {
        if (Test-PortOpen "127.0.0.1" 3306) {
            Write-Host "MariaDB já está rodando na porta 3306."
            exit 0
        }

        if (-not (Test-Path (Join-Path $DataDir "mysql"))) {
            Write-Host "Inicializando datadir do MariaDB..."
            & $MariaInstallExe --datadir="$DataDir" --password="" --port=3306
        }

        Write-Host "Iniciando MariaDB..."
        $process = Start-Process -FilePath $MariaDbExe -ArgumentList "--datadir=`"$DataDir`"", "--port=3306", "--bind-address=127.0.0.1", "--console" -PassThru -WindowStyle Hidden

        $started = $false
        for ($i = 1; $i -le 30; $i++) {
            Start-Sleep -Seconds 1
            if (Test-PortOpen "127.0.0.1" 3306) {
                $started = $true
                break
            }
        }

        if (-not $started) {
            Write-Error "ERRO: MariaDB não subiu na porta 3306. Verifique $ErrLog"
            exit 1
        }

        $process.Id | Out-File -FilePath $PidFile -Encoding ascii -Force

        Write-Host "Configurando banco de dados e credenciais..."
        $sql = @"
CREATE DATABASE IF NOT EXISTS atlas_urbano CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'atlas'@'127.0.0.1' IDENTIFIED BY 'atlas';
CREATE USER IF NOT EXISTS 'atlas'@'localhost' IDENTIFIED BY 'atlas';
GRANT ALL PRIVILEGES ON atlas_urbano.* TO 'atlas'@'127.0.0.1';
GRANT ALL PRIVILEGES ON atlas_urbano.* TO 'atlas'@'localhost';
FLUSH PRIVILEGES;
"@
        $sql | & $MariaCliExe -h 127.0.0.1 -P 3306 -u root
        Write-Host "MariaDB pronto e configurado com sucesso!"
    }

    "stop" {
        if (Test-PortOpen "127.0.0.1" 3306) {
            Write-Host "Parando MariaDB..."
            try {
                & $MariaAdminExe -h 127.0.0.1 -P 3306 -u root shutdown
                Write-Host "MariaDB finalizado via admin shutdown."
            } catch {
                # Fallback to process termination
            }
            Start-Sleep -Seconds 2
            if (Test-Path $PidFile) {
                try {
                    $pidNum = (Get-Content $PidFile -Raw).Trim()
                    Stop-Process -Id $pidNum -Force -ErrorAction SilentlyContinue
                    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
                } catch {}
            }
            Get-Process -Name "mariadbd", "mysqld" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
            Write-Host "MariaDB parado."
        } else {
            Get-Process -Name "mariadbd", "mysqld" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
            Write-Host "MariaDB já está parado."
        }
    }

    "status" {
        if (Test-PortOpen "127.0.0.1" 3306) {
            Write-Host "MariaDB está RODANDO na porta 3306."
        } else {
            Write-Host "MariaDB está PARADO."
        }
    }

    Default {
        Write-Host "Uso: .\scripts\db.ps1 [start|stop|status]"
    }
}
