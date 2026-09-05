"""Protect user-facing documentation from implementation-detail regressions."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def _visible_html() -> str:
    html = (ROOT / "docs" / "documentation.html").read_text(encoding="utf-8")
    body = html.split("<body", 1)[-1]
    body = re.sub(r"<script\b.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style\b.*?</style>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    return body


class TestUserFacingDocumentationBoundary(unittest.TestCase):
    """DC-5: user help describes the product, not source-code implementation."""

    def test_documentation_has_no_internal_code_surface(self):
        body = _visible_html()
        forbidden = {
            "python module launch path": r"python\s+-m\s+zbemt\.",
            "config object attribute": r"\bcfg\.[A-Za-z_]",
            "test project": r"projects/test\d+",
            "internal solver wording": r"\binternal solver\b",
            "internal engine wording": r"\binternal engine\b",
            "display-to-key implementation mapping": r"internal solver keys",
            "implementation wording": r"\bthe implementation\b",
            "vectorized implementation wording": r"\bvectorized over\b",
            "function execution wording": r"the function executes",
        }
        for label, pattern in forbidden.items():
            with self.subTest(label=label):
                self.assertIsNone(re.search(pattern, body, flags=re.I), label)

    def test_popup_copy_has_no_internal_optimization_explanation(self):
        source = (ROOT / "zbemt" / "gui" / "help_content.py").read_text(encoding="utf-8")
        for phrase in (
            "search minimizes internally",
            "reaches the engine only through",
            "engine reads the pair",
            "FULL CROSS PRODUCT",
            "comparison MEANS",
            "when THIS changes",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, source)

    def test_block_help_avoids_engine_implementation_language(self):
        source = (ROOT / "zbemt" / "gui" / "help_blocks.py").read_text(encoding="utf-8")
        for phrase in (
            "Everything else in the engine",
            "engine sign flipped",
            "engine interpolates",
            "engine assigns each blade element",
            "the engine floors",
            "the engine only ever sees",
            "In the code F multiplies",
            "bilinear interpolation in the extra axis",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, source)


if __name__ == "__main__":
    unittest.main()
