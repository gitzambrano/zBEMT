"""PyQt6 graphical interface.

`app` provides the main window and the workflow's seven tabs
(Project -> Geometry -> Airfoil -> Config/Motor -> Run Case -> Run Batch ->
Results). Importing this package does NOT import PyQt6 -- use
`from zbemt.gui.app import main` or the `zbemt-gui` entry point.
"""

__all__ = ["app", "styles"]
