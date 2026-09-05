"""Keep user-facing documentation separate from source-code internals."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

from zbemt.gui.help_blocks import BLOCK_HELP
from zbemt.gui.help_content import FIELD_HELP

ROOT = Path(__file__).resolve().parents[2]


def _visible_html() -> str:
    html = (ROOT / "docs" / "documentation.html").read_text(encoding="utf-8")
    body = html.split("<body", 1)[-1]
    body = re.sub(r"<script\b.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style\b.*?</style>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    return body


def _flatten_strings(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_flatten_strings(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_flatten_strings(v) for v in value)
    return ""


class TestUserFacingDocumentationBoundary(unittest.TestCase):
    """DC-5 permits useful engine explanations but not source-code internals."""

    def test_documentation_has_no_source_code_surface(self):
        body = _visible_html()
        forbidden = {
            "python module launch path": r"python\s+-m\s+zbemt\.",
            "config object attribute": r"\bcfg\.[A-Za-z_]",
            "test project": r"projects/test\d+",
            "source module path": r"\bzbemt\.(?:gui|cli|core|solver)(?:\.[A-Za-z_][A-Za-z0-9_]*)+",
            "python source file": r"\b[A-Za-z_][A-Za-z0-9_]*\.py\b",
        }
        for label, pattern in forbidden.items():
            with self.subTest(label=label):
                self.assertIsNone(re.search(pattern, body, flags=re.I), label)

    def test_popup_copy_has_no_requirement_ids_or_source_objects(self):
        visible_help = _flatten_strings(FIELD_HELP) + "\n" + _flatten_strings(BLOCK_HELP)
        forbidden = {
            "requirement id": r"\b(?:SC|DC|FR|SR)-\d+\b",
            "config object attribute": r"\bcfg\.[A-Za-z_]",
            "python module path": r"\bzbemt\.(?:gui|cli|core|solver)\.",
            "test project": r"projects/test\d+",
        }
        for label, pattern in forbidden.items():
            with self.subTest(label=label):
                self.assertIsNone(re.search(pattern, visible_help), label)


if __name__ == "__main__":
    unittest.main()
