"""
zBEMT — BEMT (Blade Element Momentum Theory) solver for rotors and
propellers.

Layers (see README.md and CLAUDE.md):

    gui/ ─┐
          ├──►  api  ──►  studies  ──►  bemt (engine)
    cli ──┘                    │
                               ├──► geometry          (3D blade geometry)
                               ├──► airfoils          (2D profile + polars)
                               └──► external_solvers  (NeuralFoil)

`api` is the only path through which the GUI and CLI run the engine or
touch disk. `studies` orchestrates `bemt` across flight conditions and
never writes to disk. `models` holds the dataclasses and the `.bemt`
serialization, with no physics at all.
"""

__version__ = "0.1.0"

__all__ = [
    "api", "bemt", "models", "validation", "geometry", "airfoils",
    "external_solvers", "studies",
]
