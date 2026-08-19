"""Shared pytest collection configuration.

Only handles import side effects that need to happen before any test
touches matplotlib/Qt -- shared `Project` constructors live in
`tests/helpers.py` (plain functions, not pytest fixtures), because the
suite also runs under `python -m unittest`, which does not execute
conftest.py.
"""
import os

import matplotlib
matplotlib.use("Agg")

# GUI tests (test_gui_smoke.py) should not need a real display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The "offscreen" platform does NOT see the system fonts on its own:
# without this it falls back to a fallback font whose glyphs come out as
# empty rectangles ("tofu") and, worse for a layout test, MUCH wider
# than the real ones -- the same QComboBox measures 265px with the real
# font and 464px without it. Any width assertion turns into noise.
# Pointing at the OS font directory gives the headless run real metrics.
for _dir_de_fontes in ("C:/Windows/Fonts", "/usr/share/fonts",
                        "/System/Library/Fonts"):
    if os.path.isdir(_dir_de_fontes):
        os.environ.setdefault("QT_QPA_FONTDIR", _dir_de_fontes)
        break
