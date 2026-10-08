"""Comandos de operação.

  python -m app.cli seed [--demo] [--st-mode mock|bling|disabled]
  python -m app.cli create-user --role admin --email x@y --name "Nome" [--customer-id ID]
  python -m app.cli process-jobs          # processa a fila de integração (cron a cada 1-5 min)
  python -m app.cli sync-status           # lê situação dos pedidos no ERP (cron)
  python -m app.cli gen-keys              # gera APP_SECRET_KEY e APP_ENCRYPTION_KEY
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys

from cryptography.fernet import Fernet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed")
    p_seed.add_argument("--demo", action="store_true", help="cria vendedor/PDV de demonstração")
    p_seed.add_argument("--st-mode", default="mock", choices=["mock", "bling", "disabled"])

    p_user = sub.add_parser("create-user")
    p_user.add_argument("--role", required=True, choices=["admin", "seller", "customer"])
    p_user.add_argument("--email", required=True)
    p_user.add_argument("--name", required=True)
    p_user.add_argument("--customer-id")

    sub.add_parser("process-jobs")
    sub.add_parser("sync-status")
    sub.add_parser("gen-keys")

    args = parser.parse_args(argv)

    if args.cmd == "gen-keys":
        print(f"APP_SECRET_KEY={secrets.token_urlsafe(48)}")
        print(f"APP_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
        return 0

    from app.config import get_settings
    from app.db import SessionLocal, get_engine

    get_settings().require_secrets()
    get_engine()
    db = SessionLocal()
    try:
        if args.cmd == "seed":
            from app.seed import seed, seed_demo
            tenant = seed(db, admin_email=os.getenv("SEED_ADMIN_EMAIL"), admin_password=os.getenv("SEED_ADMIN_PASSWORD"), st_mode=args.st_mode)
            if args.demo:
                pwd = os.getenv("SEED_DEMO_PASSWORD")
                if not pwd:
                    print("Defina SEED_DEMO_PASSWORD para criar usuários de demonstração.", file=sys.stderr)
                    return 2
                seed_demo(db, tenant, pwd)
            print(f"Seed concluído (tenant {tenant.slug}).")
        elif args.cmd == "create-user":
            from sqlalchemy import select
            from app.models import Tenant, User
            from app.security import hash_password
            tenant = db.scalar(select(Tenant).where(Tenant.slug == get_settings().default_tenant_slug))
            if tenant is None:
                print("Rode o seed antes.", file=sys.stderr)
                return 2
            pwd = getpass.getpass("Senha (mín. 8): ")
            if len(pwd) < 8:
                print("Senha curta.", file=sys.stderr)
                return 2
            db.add(User(tenant_id=tenant.id, role=args.role, name=args.name, email=args.email.lower(), password_hash=hash_password(pwd), customer_id=args.customer_id))
            db.commit()
            print("Usuário criado.")
        elif args.cmd == "process-jobs":
            from app.erp.jobs import process_pending
            done = process_pending(db)
            for j in done:
                print(f"{j.id} {j.status} {j.last_error or ''}")
            print(f"{len(done)} job(s) processado(s).")
        elif args.cmd == "sync-status":
            from sqlalchemy import select
            from app.erp.jobs import sync_order_statuses
            from app.models import ErpConnection
            total = 0
            for conn in db.scalars(select(ErpConnection).where(ErpConnection.is_active.is_(True))):
                total += sync_order_statuses(db, conn)
            print(f"{total} pedido(s) com status atualizado.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
