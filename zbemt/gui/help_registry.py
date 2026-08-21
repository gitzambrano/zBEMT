"""Extract short field descriptions from the authoritative HTML documentation.

The module reads ``docs/documentation.html`` and returns a cached mapping from each
field name to sanitized HTML text and its documentation anchor. GUI help components
use this mapping for hover text; ``field_help_data.py`` resolves sections and
``help_popup.py`` renders them. The parser accepts the documented field-row pattern
and fails closed with an empty mapping when documentation is unavailable. It is a
presentation helper, not a completeness validator, and maintains no independent
physics database.
"""
from __future__ import annotations

import re
from functools import lru_cache

#: `<tr id="ajuda-{campo}" data-ajuda-campo="...">`<td><code>...</code></td>
#: `<td>{description}</td></tr>` -- the same row that gives the anchor in
#: `field_help.mapa_de_campos()`, here also capturing the body of the
#: second cell (the explanation itself).
_LINHA_DE_AJUDA = re.compile(
    r'<tr id="ajuda-[\w.]+"[^>]*><td>.*?</td><td>(.*?)</td></tr>', re.DOTALL)
_CAMPO_DA_LINHA = re.compile(r'data-ajuda-campo="([\w.]+)"')


@lru_cache(maxsize=1)
def registro_de_campos() -> dict:
    """``{field_name: html_description}``, derived from
    ``docs/documentation.html``.

    The description is the first sentence of the field's own section --
    the same section the "open full documentation" link goes to. Empty
    dict if the documentation is not available: whoever uses this (the
    "?" tooltip) already has a generic fallback, so it is never
    mandatory.
    """
    # `field_help_data` (not `field_help`): the mapping is pure text
    # parsing with no Qt dependency, and this function must keep working
    # on a machine with no PyQt6 installed -- the engine/CLI CI job, or
    # a headless batch server.
    try:
        from .field_help_data import mapa_de_campos, secoes_da_documentacao
    except Exception:                                   # pragma: no cover
        return {}

    try:
        secoes = {a: s for s in secoes_da_documentacao()
                  for a in set(s.apelidos) | {s.ancora}}
        mapa = mapa_de_campos()
    except Exception:                                   # pragma: no cover
        return {}

    registro: dict = {}
    for campo, ancora in mapa.items():
        secao = secoes.get(ancora)
        if secao is None:
            continue
        frase = _primeira_frase(secao.corpo)
        if frase:
            registro[campo] = frase
    return registro


#: Opening paragraph of a section, skipping any figure or heading before it.
_PARAGRAFO = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL)

#: The field sections open with a bold lead-in ("The physics.", "What it
#: is.") that labels the paragraph rather than describing the field.
_ROTULO = re.compile(r"^\s*<b>[^<]{0,40}</b>\s*")


def _primeira_frase(corpo: str) -> str:
    """First sentence of the first real paragraph of ``corpo``."""
    for m in _PARAGRAFO.finditer(corpo):
        texto = _ROTULO.sub("", m.group(1)).strip()
        if len(texto) < 25:
            continue
        # cut at the first full stop that ends a sentence, keeping any
        # inline markup that opened before it
        corte = re.search(r"\.(?=\s|$)", re.sub(r"<[^>]+>", lambda x: " " * len(x.group(0)), texto))
        return (texto[:corte.end()] if corte else texto).strip()
    return ""


def descricao_curta(campo: str) -> str | None:
    """ONE-line description for ``campo`` (name suffix, e.g.
    ``"n_blades"`` from ``"geometry.n_blades"``), or ``None`` if there
    is no entry -- never raises, a field without a description just
    falls back to the caller's generic text."""
    nome = campo.split(".")[-1]
    return registro_de_campos().get(nome)
