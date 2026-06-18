"""Autenticação por equipe na borda (task_11 / ADR-006).

Substitui o "trust-on-LAN" por uma credencial por equipe, proporcional ao risco
LAN (sem mTLS/JWT). Os tokens vêm de um secret (arquivo montado, ex.: Docker
secret) ou de env — nunca de valores versionados.

Modos (env ``AUTH_MODE``):
- ``off``    — não valida (compatibilidade).
- ``warn``   — valida e contabiliza/loga ausência/invalidez, mas não bloqueia
               (transição). **Default.**
- ``enforce``— rejeita 401 quando o token é ausente/ inválido.

O token é lido do header ``X-API-Key`` ou ``Authorization: Bearer <token>``. A
equipe resolvida é registrada em ``team_var`` para auditoria; a atribuição por
hostname (ADR-003) permanece intacta.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, Optional

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.utils.logging_context import team_var
from app.utils.metrics import AUTH_DENIED_TOTAL, AUTH_OK_TOTAL

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = ("/health", "/metrics", "/docs", "/openapi", "/redoc")


def load_team_tokens() -> Dict[str, str]:
    """Carrega o mapa ``token -> team`` de um secret (arquivo) ou env.

    Prioridade: ``AUTH_TOKENS_FILE`` (JSON ``{team: token}`` ou linhas
    ``team:token``) > ``AUTH_TOKENS`` (``team1:tok1,team2:tok2``) > vazio.
    """
    path = os.getenv("AUTH_TOKENS_FILE")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            raw = fh.read().strip()
        try:
            data = json.loads(raw)
            return {tok: team for team, tok in data.items()}
        except json.JSONDecodeError:
            return _parse_pairs(raw.replace("\n", ","))
    inline = os.getenv("AUTH_TOKENS")
    if inline:
        return _parse_pairs(inline)
    return {}


def _parse_pairs(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for pair in text.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        team, tok = pair.split(":", 1)
        out[tok.strip()] = team.strip()
    return out


def _extract_token(request: Request) -> Optional[str]:
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


class TeamAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, mode: Optional[str] = None, token_to_team: Optional[Dict[str, str]] = None):
        super().__init__(app)
        self._mode = (mode or os.getenv("AUTH_MODE", "warn")).strip().lower()
        self._tokens = token_to_team if token_to_team is not None else load_team_tokens()

    async def dispatch(self, request: Request, call_next):
        if self._mode == "off" or any(request.url.path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        token = _extract_token(request)
        team = self._tokens.get(token) if token else None

        if team is not None:
            AUTH_OK_TOTAL.inc()
            tok = team_var.set(team)
            try:
                return await call_next(request)
            finally:
                team_var.reset(tok)

        # Sem token válido.
        AUTH_DENIED_TOTAL.labels(mode=self._mode).inc()
        if self._mode == "enforce":
            return JSONResponse(status_code=401, content={"detail": "invalid or missing team token"})
        logger.warning("auth warn: requisição sem token de equipe válido em %s", request.url.path)
        return await call_next(request)
