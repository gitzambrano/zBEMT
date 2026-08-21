"""Embeds KaTeX (CSS + JS) directly into `docs/documentation.html`, from
the source files in `docs/vendor/katex/*.{css,js}`.

Why embedded instead of `<link>`/`<script src>`: the GUI's embedded help
(button "?" / F1) opens the documentation via `QDesktopServices.openUrl`
with a `file://` URL (see `zbemt/gui/common.py::open_help`). Served over
HTTP the equations rendered correctly; opened directly via `file://` they
came out as raw LaTeX -- some browsers delay or block fetching external
JS/CSS under that scheme, even when it is in the same folder. Inline
eliminates that network step entirely: the HTML parser already has
everything in hand as soon as the page loads.

Run after updating the source files in `docs/vendor/katex/`:

    python tools/katex_inline.py

Idempotent: it first tries to undo a previous injection (looking for the
HTML markers below) before applying the new one, so running it twice in a
row does not duplicate the block.

The .woff2 fonts remain external files (253 KB in total), reached by the
`@font-face` rules with paths rewritten to `vendor/katex/fonts/`, since the
rules move out of `docs/vendor/katex/` when the CSS is inlined. Only the CSS
and the JS -- together about 300 KB of text -- are worth embedding. The
`.woff`/`.ttf` variants of the upstream package are fallbacks for browsers
this documentation does not need to support and would triple the file size,
so they are not shipped.
"""
from pathlib import Path
import re

# Run with no arguments (e.g. the IDE "Run" button) embeds KaTeX into docs/documentation.html.
# Idempotent: first undoes a previous injection, then applies the new one.
DEFAULT_DOC_PATH = None  # None uses docs/documentation.html

REPO = Path(__file__).resolve().parent.parent
KATEX_DIR = REPO / "docs" / "vendor" / "katex"
DOC = Path(DEFAULT_DOC_PATH) if DEFAULT_DOC_PATH else REPO / "docs" / "documentation.html"

_INICIO = "<!-- KATEX-INLINE:INICIO -->"
_FIM = "<!-- KATEX-INLINE:FIM -->"

_LINK_ORIGINAL = (
    '<link rel="stylesheet" href="vendor/katex/katex.min.css">\n'
    '<script src="vendor/katex/katex.min.js"></script>\n'
    '<script src="vendor/katex/auto-render.min.js"></script>\n'
)


def _bloco_inline() -> str:
    css = (KATEX_DIR / "katex.min.css").read_text(encoding="utf-8")
    css = css.replace("url(fonts/", "url(vendor/katex/fonts/")
    js_katex = (KATEX_DIR / "katex.min.js").read_text(encoding="utf-8")
    js_auto = (KATEX_DIR / "auto-render.min.js").read_text(encoding="utf-8")
    return (f"{_INICIO}\n<style>\n{css}\n</style>\n"
            f"<script>\n{js_katex}\n</script>\n"
            f"<script>\n{js_auto}\n</script>\n{_FIM}\n")


def main() -> None:
    html = DOC.read_text(encoding="utf-8")

    padrao_bloco = re.compile(
        re.escape(_INICIO) + r".*?" + re.escape(_FIM) + r"\n?", re.DOTALL)
    if padrao_bloco.search(html):
        html = padrao_bloco.sub(_LINK_ORIGINAL, html, count=1)
    elif _LINK_ORIGINAL not in html:
        raise SystemExit(
            "Nem o link original nem o bloco inline foram encontrados em "
            "documentation.html -- o <head> mudou de formato; atualize "
            "este script antes de rodar de novo.")

    html = html.replace(_LINK_ORIGINAL, _bloco_inline())
    DOC.write_text(html, encoding="utf-8")
    print(f"KaTeX embutido em {DOC} ({len(html)} caracteres).")


if __name__ == "__main__":
    main()
