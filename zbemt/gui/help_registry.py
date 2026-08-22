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

#: `<tr id="ajuda-{field}" data-ajuda-campo="...">`<td><code>...</code></td>
#: `<td>{description}</td></tr>` -- the same row that gives the anchor in
#:     `field_help.field_map()`, here also capturing the body of the
#: second cell (the explanation itself).
_HELP_LINE = re.compile(
    r'<tr id="ajuda-[\w.]+"[^>]*><td>.*?</td><td>(.*?)</td></tr>', re.DOTALL)
_ROW_FIELD_RE = re.compile(r'data-ajuda-campo="([\w.]+)"')


@lru_cache(maxsize=1)
def field_registry() -> dict:
    """``{field_name: html_description}``, derived from
    ``docs/documentation.html``.

    The description is the first sentence of the field's own section,
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
        from .field_help_data import field_map, documentation_sections
    except Exception:                                   # pragma: no cover
        return {}

    try:
        sections = {a: s for s in documentation_sections()
                  for a in set(s.aliases) | {s.anchor}}
        mapping = field_map()
    except Exception:                                   # pragma: no cover
        return {}

    descriptions: dict = {}
    for field, anchor in mapping.items():
        section = sections.get(anchor)
        if section is None:
            continue
        sentence = _first_sentence(section.body)
        if sentence:
            descriptions[field] = sentence
    return descriptions


#: Opening paragraph of a section, skipping any figure or heading before it.
_PARAGRAPH_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL)

#: The field sections open with a bold lead-in ("The physics.", "What it
#: is.") that labels the paragraph rather than describing the field.
_LEAD_IN_RE = re.compile(r"^\s*<b>[^<]{0,40}</b>\s*")


def _first_sentence(body: str) -> str:
    """First sentence of the first real paragraph of ``body``."""
    for m in _PARAGRAPH_RE.finditer(body):
        text = _LEAD_IN_RE.sub("", m.group(1)).strip()
        if len(text) < 25:
            continue
        # cut at the first full stop that ends a sentence, keeping any
        # inline markup that opened before it
        cut_at = re.search(r"\.(?=\s|$)", re.sub(r"<[^>]+>", lambda x: " " * len(x.group(0)), text))
        return (text[:cut_at.end()] if cut_at else text).strip()
    return ""


def short_description(field: str) -> str | None:
    """One-line description for ``field`` (name suffix, for example
    ``"n_blades"`` from ``"geometry.n_blades"``), or ``None`` if there
    is no entry. Never raises: a field without a description falls
    back to the caller's generic text."""
    name = field.split(".")[-1]
    return field_registry().get(name)
