"""Validações estruturais de cadastro.

Importante: a única validação "matemática" feita aqui é o dígito verificador do CNPJ.
NÃO há validação fiscal de IE (formato por UF, situação no Sintegra/CCC): o cadastro
fica com status `pendente_conferencia` até o back-office conferir.
"""
from __future__ import annotations

import re

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

IE_CONTRIBUINTE = 1
IE_ISENTO = 2
IE_NAO_CONTRIBUINTE = 9
IE_INDICATORS = {IE_CONTRIBUINTE: "Contribuinte ICMS", IE_ISENTO: "Contribuinte isento", IE_NAO_CONTRIBUINTE: "Não contribuinte"}


def only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def is_valid_cnpj(value: str) -> bool:
    cnpj = only_digits(value)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    def digit(base: str, weights: list[int]) -> str:
        total = sum(int(d) * w for d, w in zip(base, weights))
        rest = total % 11
        return "0" if rest < 2 else str(11 - rest)

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6] + w1
    d1 = digit(cnpj[:12], w1)
    d2 = digit(cnpj[:12] + d1, w2)
    return cnpj[-2:] == d1 + d2


def format_cnpj(value: str) -> str:
    c = only_digits(value)
    if len(c) != 14:
        return value
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def normalize_ie(indicator: int, ie: str | None) -> tuple[str | None, str | None]:
    """Retorna (ie_normalizada, erro). Regras estruturais apenas:
    1 contribuinte -> IE obrigatória (não pode ser 'ISENTO')
    2 isento       -> IE gravada como 'ISENTO'
    9 não contrib. -> IE vazia
    """
    if indicator not in IE_INDICATORS:
        return None, "Indicador de IE inválido (use 1, 2 ou 9)."
    raw = (ie or "").strip().upper()
    if indicator == IE_CONTRIBUINTE:
        if not raw or raw == "ISENTO":
            return None, "Contribuinte ICMS exige Inscrição Estadual. Se o cliente é isento, use o indicador 2."
        cleaned = re.sub(r"[^0-9A-Z]", "", raw)
        if not cleaned:
            return None, "Inscrição Estadual inválida."
        return cleaned, None
    if indicator == IE_ISENTO:
        return "ISENTO", None
    return None, None
