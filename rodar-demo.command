#!/bin/bash
# Roda o portal em modo DEMONSTRAÇÃO no seu computador (Mac ou Linux).
# Dados de teste, Bling simulado (nenhum pedido vai para o Bling de verdade).
# No Mac: dê dois cliques neste arquivo (ou arraste para o Terminal e aperte Enter).
set -e
cd "$(dirname "$0")"

echo ""
echo "=== Portal The Bulldog — demonstração ==="

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo ""
  echo "Precisa do Python 3.10 ou mais novo."
  echo "Baixe e instale em: https://www.python.org/downloads/  (botão amarelo 'Download Python')"
  echo "Depois rode este arquivo de novo."
  read -r -p "Aperte Enter para fechar." _
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Preparando o ambiente (só na primeira vez, leva 1-2 minutos)..."
  "$PY" -m venv .venv
fi
source .venv/bin/activate
pip install -q --disable-pip-version-check -r requirements.txt

if [ ! -f .env ]; then
  python -m app.cli gen-keys > .env
  cat >> .env <<'EOF'
APP_ENV=development
DATABASE_URL=sqlite:///./demo.db
SEED_ADMIN_EMAIL=admin@demo.local
SEED_ADMIN_PASSWORD=bulldog123
SEED_DEMO_PASSWORD=bulldog123
APP_PROCESS_JOBS_INLINE=true
EOF
fi

alembic upgrade head >/dev/null
python -m app.cli seed --demo --st-mode mock

echo ""
echo "Pronto! Abrindo http://localhost:8000"
echo ""
echo "  Admin (back-office): admin@demo.local    / bulldog123"
echo "  Vendedor:            vendedor@demo.local / bulldog123"
echo "  Cliente (PDV):       pdv@demo.local      / bulldog123"
echo ""
echo "Para encerrar: feche esta janela (ou Ctrl+C)."
echo ""

( sleep 2; (command -v open >/dev/null && open http://localhost:8000) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8000) || true ) &
exec uvicorn app.main:create_app --factory --port 8000
