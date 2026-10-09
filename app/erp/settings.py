"""Parâmetros configuráveis por conexão ERP.

Tudo que depende da conta Bling (ST Nicolas hoje, DFJ amanhã) fica aqui — nada é
hard-code no domínio. Campos marcados PENDENTE_DFJ só serão preenchidos após o
diagnóstico da conta Bling da DFJ e a orientação da contabilidade.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

DEFAULT_CONNECTION_SETTINGS: dict = {
    # Situação em que o pedido nasce no Bling. 21 = "Em digitação" na conta ST Nicolas.
    "order_initial_status_id": 21,
    # loja.id do pedido (opcional).
    "store_id": None,
    # PENDENTE_DFJ: natureza de operação (define CFOP/ST na nota). Se None, não é enviada.
    "operation_nature_id": None,
    # PENDENTE: natureza de operação dos pedidos da TABACARIA (sem ST, IPI destacado).
    # Se None, não é enviada (nunca herda a natureza do energético).
    "operation_nature_id_tabacaria": None,
    # Natureza do PEDIDO DE BONIFICAÇÃO (caixa bônus da campanha), quando bonus_line_mode = "separate_order".
    # O Bling aceita uma natureza por pedido; por isso a bonificação vira um pedido próprio ("<número>-B").
    "operation_nature_id_bonus": None,
    # Se True, um pedido cuja linha não tenha natureza configurada fica na fila com erro (não é enviado).
    "require_operation_nature": False,
    # PENDENTE_DFJ: depósito de saída. Guardado para uso futuro; a V1 não lança estoque.
    "warehouse_id": None,
    # PENDENTE_DFJ: transporte.fretePorConta (0 remetente, 1 destinatário, 2 terceiros,
    # 3 próprio remetente, 4 próprio destinatário, 9 sem frete). Se None, não é enviado.
    "freight_payer_code": None,
    # tiposContato "Cliente" para marcar contatos criados pelo portal (ST: 14582035035).
    "contact_type_customer_id": None,
    # Valor técnico por lata enviado ao item do Bling:
    #  "commercial" = mesmo preço comercial por lata (ex.: 5,90)
    #  "override"   = valor por SKU definido em technical_unit_price_overrides
    "technical_price_mode": "commercial",
    "technical_unit_price_overrides": {},
    # Caixa bônus: "separate_item"   = linha própria no mesmo pedido, com valor técnico abaixo;
    #              "separate_order"  = PEDIDO DE BONIFICAÇÃO separado (natureza operation_nature_id_bonus),
    #                                  valor técnico = preço por lata (ou bonus_technical_unit_value se > 0);
    #              "observation_only" = só descrita nas observações (back-office lança).
    "bonus_line_mode": "separate_item",
    "bonus_technical_unit_value": "0",
    # Enviar ao Bling pedidos de clientes ainda pendentes de conferência.
    "send_pending_customers": True,
    # PENDENTE_DFJ: IDs de formas de pagamento (preparado; a V1 não gera parcelas).
    "payment_method_ids": {"pix": None, "boleto": None, "transferencia": None},
    # Situação do Bling -> status do portal.
    "status_map": {
        "21": "enviado_erp",
        "6": "em_conferencia",
        "15": "em_conferencia",
        "24": "aprovado",
        "18": "aprovado",
        "9": "faturado",
        "12": "cancelado",
    },
    # Somente modo mock: força falha para testar reprocessamento.
    "mock_fail": False,
}

PENDING_FOR_DFJ = ("operation_nature_id", "operation_nature_id_tabacaria", "operation_nature_id_bonus", "freight_payer_code", "contact_type_customer_id")

_INT_OR_NONE = ("order_initial_status_id", "store_id", "operation_nature_id", "operation_nature_id_tabacaria", "operation_nature_id_bonus", "warehouse_id", "freight_payer_code", "contact_type_customer_id")


class SettingsError(ValueError):
    pass


def merged(settings: dict | None) -> dict:
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_CONNECTION_SETTINGS.items()}
    for k, v in (settings or {}).items():
        out[k] = v
    return out


def _to_int_or_none(value):
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise SettingsError(f"Valor inteiro inválido: {value!r}")


def _to_decimal_str(value) -> str:
    try:
        d = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError):
        raise SettingsError(f"Valor numérico inválido: {value!r}")
    if d < 0:
        raise SettingsError("Valor não pode ser negativo.")
    return str(d)


def validate(update: dict) -> dict:
    """Valida e normaliza um patch de configurações vindo do admin."""
    clean: dict = {}
    for key, value in update.items():
        if key not in DEFAULT_CONNECTION_SETTINGS:
            raise SettingsError(f"Configuração desconhecida: {key}")
        if key in _INT_OR_NONE:
            clean[key] = _to_int_or_none(value)
        elif key == "technical_price_mode":
            if value not in ("commercial", "override"):
                raise SettingsError("technical_price_mode deve ser 'commercial' ou 'override'.")
            clean[key] = value
        elif key == "bonus_line_mode":
            if value not in ("separate_item", "separate_order", "observation_only"):
                raise SettingsError("bonus_line_mode deve ser 'separate_item', 'separate_order' ou 'observation_only'.")
            clean[key] = value
        elif key == "bonus_technical_unit_value":
            clean[key] = _to_decimal_str(value)
        elif key == "technical_unit_price_overrides":
            if not isinstance(value, dict):
                raise SettingsError("technical_unit_price_overrides deve ser um objeto SKU -> valor.")
            clean[key] = {str(sku): _to_decimal_str(v) for sku, v in value.items() if v not in (None, "")}
        elif key in ("send_pending_customers", "mock_fail", "require_operation_nature"):
            clean[key] = bool(value)
        elif key == "payment_method_ids":
            if not isinstance(value, dict):
                raise SettingsError("payment_method_ids deve ser um objeto.")
            clean[key] = {str(k): _to_int_or_none(v) for k, v in value.items()}
        elif key == "status_map":
            if not isinstance(value, dict):
                raise SettingsError("status_map deve ser um objeto.")
            from app.models import OrderStatus
            for portal_status in value.values():
                if portal_status not in OrderStatus.ALL:
                    raise SettingsError(f"Status do portal inválido no mapa: {portal_status}")
            clean[key] = {str(k): v for k, v in value.items()}
        else:  # pragma: no cover
            clean[key] = value
    return clean
