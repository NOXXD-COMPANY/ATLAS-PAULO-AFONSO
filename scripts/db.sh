#!/usr/bin/env bash
# Inicia/para o MariaDB local do Atlas Urbano.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATADIR="$ROOT/.mysql-data"
SOCK="$DATADIR/mysql.sock"
CONF="$ROOT/scripts/mysql-local.cnf"
mkdir -p /tmp/mariadb-tmp

case "${1:-start}" in
  start)
    if [ -S "$SOCK" ]; then echo "MariaDB já está rodando ($SOCK)"; exit 0; fi

    if [ ! -d "$DATADIR/mysql" ]; then
      echo "Inicializando data dir do MariaDB..."
      mariadb-install-db --defaults-file="$CONF" --datadir="$DATADIR" \
        --auth-root-authentication-method=normal --skip-test-db >/dev/null
    fi

    echo "Iniciando MariaDB (socket $SOCK)..."
    nohup mariadbd --defaults-file="$CONF" --datadir="$DATADIR" \
      --socket="$SOCK" --port=3306 --pid-file="$DATADIR/mysql.pid" \
      --log-error="$DATADIR/mysql.err" --bind-address=127.0.0.1 >/dev/null 2>&1 &

    for i in $(seq 1 30); do [ -S "$SOCK" ] && break; sleep 1; done
    [ -S "$SOCK" ] || { echo "ERRO: MariaDB não subiu. Veja $DATADIR/mysql.err"; exit 1; }

    mariadb --socket="$SOCK" -u root <<'SQL'
CREATE DATABASE IF NOT EXISTS atlas_urbano CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'atlas'@'127.0.0.1' IDENTIFIED BY 'atlas';
CREATE USER IF NOT EXISTS 'atlas'@'localhost' IDENTIFIED BY 'atlas';
GRANT ALL PRIVILEGES ON atlas_urbano.* TO 'atlas'@'127.0.0.1';
GRANT ALL PRIVILEGES ON atlas_urbano.* TO 'atlas'@'localhost';
FLUSH PRIVILEGES;
SQL
    echo "MariaDB pronto."
    ;;
  stop)
    if [ -S "$SOCK" ]; then
      mariadb-admin --socket="$SOCK" -u root shutdown
      echo "MariaDB parado."
    else
      echo "MariaDB já está parado."
    fi
    ;;
  *)
    echo "Uso: $0 [start|stop]"
    exit 1
    ;;
esac