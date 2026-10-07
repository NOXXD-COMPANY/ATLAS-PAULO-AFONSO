"""Supervisor local do Atlas Urbano de Paulo Afonso.
Inicia e mantem ativos:
1. MariaDB (porta 3306)
2. Backend FastAPI (porta 8000)
3. Frontend Vite (porta 5173)
"""

import os
import sys
import time
import socket
import subprocess
import signal

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, ".mysql-data")
MARIADB_DIR = r"C:\Program Files\MariaDB 13.0\bin"
MARIADBD_EXE = os.path.join(MARIADB_DIR, "mariadbd.exe")
MARIADB_INSTALL_EXE = os.path.join(MARIADB_DIR, "mariadb-install-db.exe")
MARIADB_CLI_EXE = os.path.join(MARIADB_DIR, "mariadb.exe")

VENV_PYTHON = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

processes = []


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def wait_for_port(host: str, port: int, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(host, port):
            return True
        time.sleep(1)
    return False


def setup_mariadb():
    os.makedirs(DATA_DIR, exist_ok=True)
    mysql_sub = os.path.join(DATA_DIR, "mysql")
    if not os.path.exists(mysql_sub):
        print("==> Inicializando diretorio de dados do MariaDB...")
        cmd = [MARIADB_INSTALL_EXE, f"--datadir={DATA_DIR}", "--password=", "--port=3306"]
        subprocess.run(cmd, check=True)

    if not is_port_open("127.0.0.1", 3306):
        print("==> Iniciando MariaDB (porta 3306)...")
        err_log = open(os.path.join(DATA_DIR, "mysql.err"), "a", encoding="utf-8")
        mariadb_cmd = [
            MARIADBD_EXE,
            f"--datadir={DATA_DIR}",
            "--port=3306",
            "--bind-address=127.0.0.1",
            "--console",
        ]
        p = subprocess.Popen(mariadb_cmd, stdout=err_log, stderr=err_log, cwd=ROOT_DIR)
        processes.append(p)
        if not wait_for_port("127.0.0.1", 3306, 30):
            raise RuntimeError("MariaDB nao respondeu na porta 3306.")
        print("  MariaDB pronto!")

    # Configura usuario e database se necessario
    init_sql = """
CREATE DATABASE IF NOT EXISTS atlas_urbano CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'atlas'@'127.0.0.1' IDENTIFIED BY 'atlas';
CREATE USER IF NOT EXISTS 'atlas'@'localhost' IDENTIFIED BY 'atlas';
GRANT ALL PRIVILEGES ON atlas_urbano.* TO 'atlas'@'127.0.0.1';
GRANT ALL PRIVILEGES ON atlas_urbano.* TO 'atlas'@'localhost';
FLUSH PRIVILEGES;
"""
    subprocess.run(
        [MARIADB_CLI_EXE, "-h", "127.0.0.1", "-P", "3306", "-u", "root"],
        input=init_sql.encode("utf-8"),
        capture_output=True,
    )


def ensure_data():
    import pymysql

    try:
        conn = pymysql.connect(
            host="127.0.0.1",
            port=3306,
            user="atlas",
            password="atlas",
            database="atlas_urbano",
        )
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM buildings")
            count = cur.fetchone()[0]
        conn.close()
        if count > 0:
            print(f"==> Base de dados pronta: {count:,} edificacoes em 'buildings'.")
            return
    except Exception:
        pass

    print("==> Importando dados (import_data.py)...")
    subprocess.run([VENV_PYTHON, os.path.join(ROOT_DIR, "import_data.py")], check=True)


def start_backend():
    if is_port_open("127.0.0.1", 8000):
        print("==> Backend ja esta em execucao na porta 8000.")
        return

    print("==> Iniciando Backend FastAPI (porta 8000)...")
    b_out = open(os.path.join(ROOT_DIR, "backend.log"), "a", encoding="utf-8")
    b_cmd = [
        VENV_PYTHON,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    p = subprocess.Popen(b_cmd, stdout=b_out, stderr=b_out, cwd=ROOT_DIR)
    processes.append(p)
    if not wait_for_port("127.0.0.1", 8000, 20):
        raise RuntimeError("Backend nao respondeu na porta 8000.")
    print("  Backend FastAPI pronto!")


def start_frontend():
    if is_port_open("127.0.0.1", 5173):
        print("==> Frontend ja esta em execucao na porta 5173.")
        return

    print("==> Iniciando Frontend Vite (porta 5173)...")
    f_out = open(os.path.join(ROOT_DIR, "frontend.log"), "a", encoding="utf-8")
    # Usa npx/npm com shell=True no Windows
    f_cmd = "npm run dev -- --port 5173 --host 127.0.0.1"
    p = subprocess.Popen(f_cmd, stdout=f_out, stderr=f_out, cwd=FRONTEND_DIR, shell=True)
    processes.append(p)
    if not wait_for_port("127.0.0.1", 5173, 20):
        raise RuntimeError("Frontend nao respondeu na porta 5173.")
    print("  Frontend Vite pronto!")


def stop_all(sig=None, frame=None):
    print("\nEncerrando servicos do Atlas Urbano...")
    for p in reversed(processes):
        try:
            p.terminate()
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    print("=" * 60)
    print("      Atlas Urbano de Paulo Afonso — Servidor Local")
    print("=" * 60)

    setup_mariadb()
    ensure_data()
    start_backend()
    start_frontend()

    print("\n" + "=" * 60)
    print("  PROJETO PRONTO PARA APRESENTACAO NO LOCALHOST!")
    print("=" * 60)
    print("  Frontend (Mapa e Relatorio): http://127.0.0.1:5173/")
    print("  Backend (API GeoJSON):       http://127.0.0.1:8000/")
    print("  Documentacao OpenAPI:        http://127.0.0.1:8000/docs")
    print("=" * 60)
    print("Pressione Ctrl+C para encerrar os servicos.\n")

    # Monitora os processos
    while True:
        for p in processes:
            ret = p.poll()
            if ret is not None:
                print(f"Aviso: Processo PID {p.pid} finalizou com codigo {ret}.")
        time.sleep(2)


if __name__ == "__main__":
    main()
