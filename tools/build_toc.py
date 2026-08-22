"""Regenerates the table of contents at the top of ``docs/documentation.html``.

The document is long enough that a reader who knows what they are looking for
should not have to scroll to find it. The index is DERIVED from the headings
actually present, so it cannot fall out of step with the document the way a
hand-maintained list would -- the same reason ``tools/field_index.py`` derives
the per-tab field lists from the running GUI.

Two levels: chapters (``<h2>``) and their sections (``<h3>``). Deeper
headings are deliberately left out; at four levels the index stops being
easier to scan than the document.

A heading with no anchor of its own, and none immediately before it, gets a
slug id injected so it can be linked. That is the only edit made outside the
index block itself.

    python tools/build_toc.py            # shows what would change
    python tools/build_toc.py --write    # writes it
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "documentation.html"

#: Zero-argument run is a dry run, like tools/field_index.py.
DEFAULT_WRITE_MODE = False

MARK_START = "<!-- INDICE-GERAL -->"
MARK_END = "<!-- /INDICE-GERAL -->"

#: A heading, with its own id when it has one.
_HEADING = re.compile(r'<h([23])(?:\s+id="([\w-]+)")?[^>]*>(.*?)</h\1>', re.S)

#: `<a id="x"></a>` used as an anchor immediately before a heading.
_FREE_ANCHOR = re.compile(r'<a id="([\w-]+)"></a>')


def _text(raw: str) -> str:
    """Heading text with the markup removed, entities left readable."""
    clean = re.sub(r"<[^>]+>", "", raw)
    clean = clean.replace("&mdash;", "—").replace("&rarr;", "→")
    clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return " ".join(clean.split())


def _slug(text: str) -> str:
    base = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    base = re.sub(r"[^\w\s-]", "", base).strip().lower()
    return "sec-" + re.sub(r"[\s_]+", "-", base)[:48].strip("-")


def collect(html: str):
    """[(level, anchor, text)] in document order, injecting ids when needed.

    Returns the (possibly edited) html alongside the entries, because giving
    an unanchored heading an id is part of making the index linkable.
    """
    entries = []
    used = set(re.findall(r'id="([\w-]+)"', html))
    out = []
    prev_end = 0

    for m in _HEADING.finditer(html):
        level, own_anchor, raw = int(m.group(1)), m.group(2), m.group(3)
        text = _text(raw)
        if not text:
            continue

        anchor = own_anchor
        if not anchor:
            # `<a id="..."></a>` sitting just above the heading, possibly
            # several of them (the document keeps old anchors as aliases).
            before = html[max(0, m.start() - 260):m.start()]
            free = _FREE_ANCHOR.findall(before)
            if free and not _text(_FREE_ANCHOR.sub("", before)):
                anchor = free[-1]

        if not anchor:
            anchor = _slug(text)
            n = 2
            while anchor in used:
                anchor, n = f"{_slug(text)}-{n}", n + 1
            used.add(anchor)
            out.append(html[prev_end:m.start()])
            out.append(f'<h{level} id="{anchor}">{raw}</h{level}>')
            prev_end = m.end()

        entries.append((level, anchor, text))

    out.append(html[prev_end:])
    return "".join(out), entries


def render(entries) -> str:
    lines = [MARK_START, '<nav class="indice-geral" aria-label="Table of contents">',
             '<div class="indice-titulo">Contents</div>', "<ol>"]
    open_list = False
    for level, anchor, text in entries:
        if level == 2:
            if open_list:
                lines.append("</ol></li>")
                open_list = False
            lines.append(f'<li><a href="#{anchor}">{text}</a>')
            lines.append("<ol>")
            open_list = True
        else:
            lines.append(f'<li><a href="#{anchor}">{text}</a></li>')
    if open_list:
        lines.append("</ol></li>")
    lines += ["</ol>", "</nav>", MARK_END]
    return "\n".join(lines)


def apply(html: str, block: str) -> str:
    if MARK_START in html:
        start = html.index(MARK_START)
        end = html.index(MARK_END) + len(MARK_END)
        return html[:start] + block + html[end:]
    # The index goes after the title block and before the first chapter.
    # Anchoring on the first `<hr>` was wrong: inserting a chapter consumed
    # the rule that followed the title, and the index silently drifted to
    # the end of chapter 1. The first `<h2>` cannot move.
    #
    # The spacing is normalised rather than preserved, so that
    # strip-then-reinsert always lands on the same bytes; otherwise the
    # round trip differs by a newline and the sync test fails forever.
    cut = html.index("<h2")
    return html[:cut].rstrip() + "\n\n" + block + "\n\n" + html[cut:]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    write = DEFAULT_WRITE_MODE or "--write" in argv

    original = DOC.read_text(encoding="utf-8")
    # Strip any existing index BEFORE scanning, so the block never indexes
    # itself and `apply` always inserts into a clean document.
    html = original
    if MARK_START in html:
        i = html.index(MARK_START)
        j = html.index(MARK_END) + len(MARK_END)
        # Consume the newline `apply` adds after the block too, or a run
        # would insert one more each time and never reach a fixed point.
        if html[j:j + 1] == "\n":
            j += 1
        html = html[:i] + html[j:]
    html, entries = collect(html)
    new = apply(html, render(entries))

    chapters = sum(1 for n, _, _ in entries if n == 2)
    print(f"{chapters} chapters, {len(entries) - chapters} sections")
    if new == original:
        print("index already up to date")
        return 0
    if not write:
        print("(use --write to write it)")
        return 0
    DOC.write_text(new, encoding="utf-8")
    print("index written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
