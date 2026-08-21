"""Provide the GUI tabs in workflow order.

Each submodule owns one tab's widgets, event handlers, and presentation state. Tabs
receive shared application state, delegate project and solver operations through the
application boundary, and expose no independent persistence or aerodynamic model.
"""

from .project import ProjectTab
from .geometry_tab import GeometryTab
from .airfoil import AirfoilTab
from .config import ConfigMotorTab
from .run_case import RunCaseTab
from .run_batch import RunBatchTab
from .results import ResultsTab

__all__ = ["ProjectTab", "GeometryTab", "AirfoilTab", "ConfigMotorTab",
           "RunCaseTab", "RunBatchTab", "ResultsTab"]
