from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, customers, orders
from app.config import get_settings
from app.db import get_engine
from app.security import CSRF_HEADER

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def create_app() -> FastAPI:
    settings = get_settings()
    settings.require_secrets()
    get_engine()
    app = FastAPI(title="Portal Comercial The Bulldog", version="1.0.0", docs_url="/api/docs" if settings.environment != "production" else None, redoc_url=None, openapi_url="/api/openapi.json" if settings.environment != "production" else None)

    @app.middleware("http")
    async def csrf_and_headers(request: Request, call_next):
        # Mitigação de CSRF: requisições que alteram estado precisam de um cabeçalho
        # customizado, que um site de terceiros não consegue enviar sem CORS (não habilitado).
        if request.method in UNSAFE and request.url.path.startswith("/api/") and request.headers.get(CSRF_HEADER) != "1":
            return JSONResponse({"detail": "Requisição recusada (cabeçalho de segurança ausente)."}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if not request.url.path.startswith("/api/docs"):
            response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        msgs = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "header"))
            msgs.append(f"{loc}: {err.get('msg')}" if loc else err.get("msg"))
        return JSONResponse({"detail": "Dados inválidos: " + "; ".join(msgs)}, status_code=422)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    app.include_router(auth.router)
    app.include_router(customers.router)
    app.include_router(orders.router)
    app.include_router(admin.router)

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app

