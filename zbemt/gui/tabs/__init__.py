"""One tab per module, in workflow order."""

from .project import ProjectTab
from .geometry_tab import GeometryTab
from .airfoil import AirfoilTab
from .config import ConfigMotorTab
from .run_case import RunCaseTab
from .run_batch import RunBatchTab
from .results import ResultsTab

__all__ = ["ProjectTab", "GeometryTab", "AirfoilTab", "ConfigMotorTab",
           "RunCaseTab", "RunBatchTab", "ResultsTab"]
