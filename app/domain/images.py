"""Fotos dos produtos: arquivos estáticos em frontend/produtos/<SKU>.webp.

Para trocar ou incluir uma foto, basta salvar um .webp (fundo transparente, quadrado)
com o SKU como nome. Sem arquivo, o portal mostra o produto sem foto.
"""
from __future__ import annotations

from pathlib import Path

PHOTOS_DIR = Path(__file__).resolve().parents[2] / "frontend" / "produtos"


def image_url(sku: str | None) -> str | None:
    if not sku:
        return None
    path = PHOTOS_DIR / f"{sku}.webp"
    return f"produtos/{sku}.webp" if path.is_file() else None
