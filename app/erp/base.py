"""Contrato do adaptador de ERP. O domínio do portal só conversa com esta interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ErpError(Exception):
    """Erro de integração. `retryable` indica se vale reprocessar automaticamente."""

    def __init__(self, message: str, *, retryable: bool = True, status_code: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.details = details or {}


class ErpNotConfigured(ErpError):
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


@dataclass
class ErpOrderRef:
    external_id: str
    external_number: str | None = None
    status_id: int | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ErpCustomerRef:
    external_id: str
    created: bool


class ErpAdapter(Protocol):
    def find_customer_by_document(self, cnpj: str) -> str | None: ...

    def create_customer(self, payload: dict) -> str: ...

    def find_order_by_portal_number(self, portal_number: str) -> ErpOrderRef | None: ...

    def create_order(self, payload: dict) -> ErpOrderRef: ...

    def get_order(self, external_id: str) -> ErpOrderRef: ...

    def set_order_status(self, external_id: str, status_id: int) -> None: ...
