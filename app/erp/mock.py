"""Adaptador simulado para desenvolvimento e testes. Não faz nenhuma chamada externa.

Os "registros" ficam em memória por conexão (somem ao reiniciar o processo); os IDs
retornados são numéricos, como no Bling.
"""
from __future__ import annotations

import itertools
import threading

from app.erp.base import ErpError, ErpOrderRef

_lock = threading.Lock()
_seq = itertools.count(900000000001)
_state: dict[str, dict] = {}


def _bucket(connection_id: str) -> dict:
    return _state.setdefault(connection_id, {"contacts": {}, "orders": {}, "order_seq": itertools.count(1)})


def reset() -> None:
    with _lock:
        _state.clear()


class MockAdapter:
    def __init__(self, connection_id: str, settings: dict):
        self.connection_id = connection_id
        self.settings = settings
        self.calls: list[tuple[str, dict]] = []

    def _maybe_fail(self):
        if self.settings.get("mock_fail"):
            raise ErpError("Falha simulada do ERP (mock_fail=true).", retryable=True, status_code=503)

    def find_customer_by_document(self, cnpj: str) -> str | None:
        self._maybe_fail()
        return _bucket(self.connection_id)["contacts"].get(cnpj)

    def create_customer(self, payload: dict) -> str:
        self._maybe_fail()
        with _lock:
            ext = str(next(_seq))
            _bucket(self.connection_id)["contacts"][payload["numeroDocumento"]] = ext
        self.calls.append(("create_customer", payload))
        return ext

    def find_order_by_portal_number(self, portal_number: str) -> ErpOrderRef | None:
        self._maybe_fail()
        o = _bucket(self.connection_id)["orders"].get(portal_number)
        return ErpOrderRef(**o) if o else None

    def create_order(self, payload: dict) -> ErpOrderRef:
        self._maybe_fail()
        with _lock:
            b = _bucket(self.connection_id)
            ref = {"external_id": str(next(_seq)), "external_number": str(next(b["order_seq"])), "status_id": (payload.get("situacao") or {}).get("id"), "raw": {"payload": payload}}
            b["orders"][payload["numeroLoja"]] = ref
        self.calls.append(("create_order", payload))
        return ErpOrderRef(**ref)

    def get_order(self, external_id: str) -> ErpOrderRef:
        self._maybe_fail()
        for o in _bucket(self.connection_id)["orders"].values():
            if o["external_id"] == external_id:
                return ErpOrderRef(**o)
        raise ErpError("Pedido não encontrado no mock.", retryable=False, status_code=404)

    def set_order_status(self, external_id: str, status_id: int) -> None:
        for o in _bucket(self.connection_id)["orders"].values():
            if o["external_id"] == external_id:
                o["status_id"] = status_id
