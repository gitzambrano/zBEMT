"""Short per-field help content, for the "?" instant tooltip
(`field_help.py`) -- Part 1 of the documentation redesign plan
(see `production-plan.md`/session history: contextual per-field popup).

This is NOT a third hand-maintained list: the ONE-line explanation per
field already exists in `docs/documentation.html`, in the "Parameters by
tab" table (`guia-campos` section, `id="ajuda-{campo}"`, the same source
`field_help.mapa_de_campos()` uses to find the ANCHOR). This module just
reads the same table and returns the TEXT of the cell next to it --
crossing the same source twice instead of duplicating the content in
Python is what avoids the "third list that ages silently with every new
field" that the plan itself warns not to create.

Scope of this part of the plan: the RICH per-field popup (short
definition + "see full documentation" link, delivered via `QToolTip`
HTML on the existing "?" button -- instant on hover, no browser opening,
no new widget, no layout risk). The whole-BLOCK "?" (one explanation
per `QGroupBox`) and the full HTML restructuring (tutorial ->
fundamentals -> by tab) are bigger and are left for a dedicated
session -- see the scope note in `production-plan.md`/follow-up task.
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
    ``docs/documentation.html``. Empty dict if the documentation is not
    available -- whoever uses this (the "?" tooltip) already has a
    generic fallback text, so this is never mandatory."""
    from .. import paths

    caminho = paths.documentation_path()
    if caminho is None:
        return {}
    try:
        html = caminho.read_text(encoding="utf-8")
    except OSError:
        return {}

    registro: dict = {}
    for linha in re.finditer(r'<tr id="ajuda-[\w.]+"[^>]*>.*?</tr>', html, re.DOTALL):
        bloco = linha.group(0)
        campo_m = _CAMPO_DA_LINHA.search(bloco)
        desc_m = re.search(r'<td>(.*?)</td>\s*</tr>', bloco, re.DOTALL)
        if campo_m and desc_m:
            registro[campo_m.group(1)] = desc_m.group(1).strip()
    return registro


def descricao_curta(campo: str) -> str | None:
    """ONE-line description for ``campo`` (name suffix, e.g.
    ``"n_blades"`` from ``"geometry.n_blades"``), or ``None`` if there
    is no entry -- never raises, a field without a description just
    falls back to the caller's generic text."""
    nome = campo.split(".")[-1]
    return registro_de_campos().get(nome)
