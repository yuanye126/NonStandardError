"""nse_engine — Non-Standard Errors multiverse engine."""
from .config import Config, ConfigValidationError, compute_n_specs
from .runner import run_multiverse
from .aggregate import aggregate

__all__ = ["Config", "ConfigValidationError", "compute_n_specs", "run_multiverse", "aggregate"]
