"""Register domain executors without coupling them to the runner."""
from __future__ import annotations

from collections.abc import Callable

from .models import CheckResult, Claim, ExecutionContext


Executor = Callable[[Claim, ExecutionContext], CheckResult]


class ExecutorRegistry:
    """Store named claim executors for present and later domains."""

    def __init__(self) -> None:
        self._executors: dict[str, Executor] = {}

    def register(self, name: str, executor: Executor) -> None:
        """Register one unique executor name."""
        if not name or name == "unimplemented":
            raise ValueError("An executor needs a non-reserved name.")
        if name in self._executors:
            raise ValueError(f"Executor already registered: {name}")
        self._executors[name] = executor

    def get(self, name: str) -> Executor | None:
        """Return a registered executor or None."""
        return self._executors.get(name)


def build_executor_registry() -> ExecutorRegistry:
    """Build the registry of completed physical domain executors."""
    from .core_bemt_executor import execute_core_bemt_claim
    from .dynamic_stall_executor import DynamicStallExecutor
    from .flapping_executor import FlappingExecutor
    from .pitt_corrections_executor import execute_pitt_corrections_claim
    from .propeller_executor import PropellerExecutor

    registry = ExecutorRegistry()
    registry.register("core_bemt_executor", execute_core_bemt_claim)
    registry.register("propeller_executor", PropellerExecutor())
    registry.register("dynamic_stall_executor", DynamicStallExecutor())
    flapping_executor = FlappingExecutor()
    registry.register("flapping_executor", flapping_executor)
    registry.register("lead_lag_executor", flapping_executor)
    registry.register("stability_derivatives_executor", flapping_executor)
    registry.register("pitt_peters_executor", execute_pitt_corrections_claim)
    registry.register("model_effects_executor", execute_pitt_corrections_claim)
    registry.register("extremes_executor", execute_pitt_corrections_claim)
    return registry
