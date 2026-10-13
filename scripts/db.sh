#!/usr/bin/env bash
# Inicia/para o MariaDB local do Atlas Urbano (Porta 3307 / Windows Nativo)
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATADIR="$ROOT/.mysql-data"
CONF="$ROOT/scripts/mysql-local.cnf"
mkdir -p /tmp/mariadb-tmp

DB_PORT="3307"
ROOT_PASSWORD="ar120604"

WIN_DATADIR="$(cygpath -w "$DATADIR" 2>/dev/null || echo "$DATADIR" | sed 's|^/c/|C:/|;s|/|\\|g')"
WIN_CONF="$(cygpath -w "$CONF" 2>/dev/null || echo "$CONF" | sed 's|^/c/|C:/|;s|/|\\|g')"

MARIADBD="C:/Program Files/MariaDB 13.0/bin/mariadbd.exe"
MARIADB_CLIENT="C:/Program Files/MariaDB 13.0/bin/mariadb.exe"
MARIADB_ADMIN="C:/Program Files/MariaDB 13.0/bin/mariadb-admin.exe"

if [ -n "$ROOT_PASSWORD" ]; then
  CLIENT_AUTH="-h 127.0.0.1 -P $DB_PORT -u root -p$ROOT_PASSWORD"
  ADMIN_AUTH="-h 127.0.0.1 -P $DB_PORT -u root -p$ROOT_PASSWORD"
else
  CLIENT_AUTH="-h 127.0.0.1 -P $DB_PORT -u root"
  ADMIN_AUTH="-h 127.0.0.1 -P $DB_PORT -u root"
fi

case "${1:-start}" in
  start)
    if [ ! -d "$DATADIR/mysql" ]; then
      echo "Inicializando data dir do MariaDB..."
      "C:/Program Files/MariaDB 13.0/bin/mariadb-install-db.exe" --datadir="$WIN_DATADIR" >/dev/null 2>&1 || \
      "$MARIADBD" --initialize-insecure --datadir="$WIN_DATADIR"
    fi

    echo "Iniciando MariaDB na porta $DB_PORT..."
    nohup "$MARIADBD" --defaults-file="$WIN_CONF" --datadir="$WIN_DATADIR" \
      --port="$DB_PORT" --pid-file="$WIN_DATADIR/mysql.pid" \
      --log-error="$WIN_DATADIR/mysql.err" --bind-address=127.0.0.1 >/dev/null 2>&1 &

    sleep 3

    echo "Configurando banco de dados e permissões..."
    "$MARIADB_CLIENT" $CLIENT_AUTH <<'SQL'
CREATE DATABASE IF NOT EXISTS atlas_urbano CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'atlas'@'127.0.0.1' IDENTIFIED BY 'atlas';
CREATE USER IF NOT EXISTS 'atlas'@'localhost' IDENTIFIED BY 'atlas';
GRANT ALL PRIVILEGES ON atlas_urbano.* TO 'atlas'@'127.0.0.1';
GRANT ALL PRIVILEGES ON atlas_urbano.* TO 'atlas'@'localhost';
FLUSH PRIVILEGES;
SQL
    echo "MariaDB pronto na porta $DB_PORT."
    ;;
  stop)
    echo "Parando MariaDB..."
    "$MARIADB_ADMIN" $ADMIN_AUTH shutdown 2>/dev/null || true
    echo "MariaDB parado."
    ;;
  *)
    echo "Uso: $0 [start|stop]"
    exit 1
    ;;
esac