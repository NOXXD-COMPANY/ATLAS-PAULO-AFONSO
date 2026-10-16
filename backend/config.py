"""Conexão com o banco (MySQL/MariaDB).

Lê de variáveis de ambiente, com fallback para os valores locais
(usados pelo scripts/run.sh). No Render, cadastre DB_HOST, DB_PORT,
DB_USER, DB_PASSWORD e DB_NAME no painel do Web Service.
"""
import os

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "3307"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "ar120604")
DB_NAME = os.environ.get("DB_NAME", "atlas_urbano")

# JWT do login. Em produção, cadastre um JWT_SECRET forte no ambiente;
# o padrão abaixo é só para desenvolvimento local.
JWT_SECRET = os.environ.get("JWT_SECRET", "atlas-urbano-dev")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))