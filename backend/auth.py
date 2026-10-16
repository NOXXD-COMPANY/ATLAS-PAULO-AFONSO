"""Cadastro e login com JWT (padrão Bearer).

Responsabilidades deste módulo:
- garantir a tabela `users` (ensure_auth_schema, na subida da API);
- transformar senha em hash bcrypt (a senha nunca é gravada nem devolvida);
- persistência e consulta de usuários (create_user, authenticate);
- emitir e validar tokens JWT (create_token, get_current_user).

Tudo passa por consultas parametrizadas, no padrão de db.py.
Fora do escopo: recuperação de senha e bloqueio por tentativas.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pymysql
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(128) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


class EmailEmUso(ValueError):
    """Cadastro com e-mail que já existe na tabela."""


def ensure_auth_schema():
    """Cria a tabela `users` se ela ainda não existir. Idempotente."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(USERS_SCHEMA)


def hash_senha(senha: str) -> str:
    """Gera o hash bcrypt da senha (salt aleatório embutido)."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def confere_senha(senha: str, senha_hash: str) -> bool:
    """Confere a senha em tempo constante contra o hash guardado."""
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("ascii"))
    except ValueError:
        return False


def _publico(row):
    """Linha do banco → dados públicos (sem nenhum vestígio da senha)."""
    return {
        "id": row["id"],
        "nome": row["nome"],
        "email": row["email"],
        "criado_em": row["criado_em"],
    }


def create_user(nome: str, email: str, senha: str):
    """Cadastra e devolve os dados públicos. Levanta EmailEmUso se duplicar."""
    email = email.strip().lower()
    try:
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (nome, email, senha_hash) VALUES (%s, %s, %s)",
                (nome.strip(), email, hash_senha(senha)),
            )
            user_id = cur.lastrowid
            cur.execute(
                "SELECT id, nome, email, criado_em FROM users WHERE id = %s",
                (user_id,),
            )
            return _publico(cur.fetchone())
    except pymysql.err.IntegrityError as e:
        if e.args and e.args[0] == 1062:  # Duplicate entry (email UNIQUE)
            raise EmailEmUso(email) from e
        raise


def authenticate(email: str, senha: str):
    """Devolve os dados públicos se e-mail + senha conferem, senão None."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, nome, email, senha_hash, criado_em FROM users "
            "WHERE email = %s",
            (email.strip().lower(),),
        )
        row = cur.fetchone()
    if row is None or not confere_senha(senha, row["senha_hash"]):
        return None
    return _publico(row)


def create_token(user_id: int) -> str:
    """Emite um JWT HS256 com o id do usuário e expiração configurável."""
    expira = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "exp": expira},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


bearer = HTTPBearer(auto_error=True)


def get_current_user(
    credenciais: HTTPAuthorizationCredentials = Depends(bearer),
):
    """Dependência das rotas protegidas: valida o Bearer e devolve o usuário.

    Sem token, expirado, adulterado ou de usuário inexistente → 401.
    """
    try:
        dados = jwt.decode(
            credenciais.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        user_id = int(dados.get("sub", ""))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="sessão inválida ou expirada")
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, nome, email, criado_em FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="sessão inválida ou expirada")
    return _publico(row)
