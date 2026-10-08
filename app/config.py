"""Configuração da aplicação lida de variáveis de ambiente.

Segredos (chave de sessão, chave de criptografia, credenciais OAuth do Bling)
existem SOMENTE no backend. Nada aqui é exposto ao frontend.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "sim"}


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./portal.db"))
    secret_key: str = field(default_factory=lambda: os.getenv("APP_SECRET_KEY", ""))
    # Chave Fernet (base64 urlsafe, 32 bytes) para criptografar tokens OAuth em repouso.
    encryption_key: str = field(default_factory=lambda: os.getenv("APP_ENCRYPTION_KEY", ""))
    session_hours: int = field(default_factory=lambda: int(os.getenv("APP_SESSION_HOURS", "12")))
    cookie_secure: bool = field(default_factory=lambda: _bool(os.getenv("APP_COOKIE_SECURE"), False))
    public_base_url: str = field(default_factory=lambda: os.getenv("APP_PUBLIC_BASE_URL", "http://localhost:8000"))
    default_tenant_slug: str = field(default_factory=lambda: os.getenv("APP_DEFAULT_TENANT", "dfj"))
    # Processa jobs de integração logo após criar o pedido (em background). Desligue
    # se for usar somente o worker/cron (python -m app.cli process-jobs).
    process_jobs_inline: bool = field(default_factory=lambda: _bool(os.getenv("APP_PROCESS_JOBS_INLINE"), True))
    environment: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))

    def require_secrets(self) -> None:
        missing = [name for name, val in (("APP_SECRET_KEY", self.secret_key), ("APP_ENCRYPTION_KEY", self.encryption_key)) if not val]
        if missing:
            raise RuntimeError(
                "Variáveis obrigatórias ausentes: " + ", ".join(missing) + ". Veja .env.example."
            )


def load_dotenv(path: str = ".env") -> None:
    """Carrega .env simples (CHAVE=valor) sem sobrescrever variáveis já definidas."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


@lru_cache
def get_settings() -> Settings:
    if os.getenv("APP_SKIP_DOTENV") != "1":
        load_dotenv()
    return Settings()


def erp_credential(prefix: str, name: str) -> str | None:
    """Lê credencial de ERP do ambiente. Ex.: prefix=BLING_STNICOLAS, name=CLIENT_ID
    -> variável BLING_STNICOLAS_CLIENT_ID. O banco guarda só o prefixo, nunca o segredo."""
    return os.getenv(f"{prefix}_{name}")
