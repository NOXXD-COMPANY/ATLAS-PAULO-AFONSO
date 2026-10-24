"""Autenticação e autorização com JWT stateless (padrão Bearer).

Os dados de cadastro e autenticação de usuários são gerenciados no cliente
(localStorage do navegador). O servidor apenas assina e valida tokens JWT,
sem tocar no banco de dados.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET


def create_token(user_id: int, nome: str = "", email: str = "") -> str:
    """Emite um JWT HS256 com os dados públicos do usuário e expiração configurável."""
    expira = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "nome": nome,
        "email": email,
        "exp": expira,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


bearer = HTTPBearer(auto_error=True)


def get_current_user(
    credenciais: HTTPAuthorizationCredentials = Depends(bearer),
) -> Dict[str, Any]:
    """Dependência das rotas protegidas: validação stateless.
    Token ausente, expirado ou adulterado → 401.
    """
    try:
        dados = jwt.decode(
            credenciais.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        return {
            "id": int(dados.get("sub", "1")),
            "nome": dados.get("nome", ""),
            "email": dados.get("email", ""),
        }
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="sessão inválida ou expirada")
