"""
Config dataclass + JSON (de)serialization + validation for NSE engine.
All dataset-specific settings live here; engine code contains no hardcoded paths or literals.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class ConfigValidationError(ValueError):
    """Raised when Config validation fails; maps to 422 in the web backend."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


# ---------------------------------------------------------------------------
# Sub-dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DatasetConfig:
    path: str
    format: str = "csv"  # csv | xlsx


@dataclass
class RolesConfig:
    dependent: str
    independent: list[str]
    time_var: Optional[str] = None
    country_var: Optional[str] = None
    instruments: list[str] = field(default_factory=list)


@dataclass
class VariableSelectionConfig:
    min_variables: int = 8
    max_correlation: float = 0.7
    required_vars: list[str] = field(default_factory=list)
    target_combinations: int = 3000
    precomputed_combos_path: Optional[str] = None


@dataclass
class DesignSpaceConfig:
    dep_na_treatment: list[str] = field(default_factory=lambda: ["omit", "zero"])
    dep_outlier: list[dict] = field(default_factory=lambda: [
        {"apply": False},
        {"apply": True, "method": "winsorize", "threshold": 0.01, "symmetric": "both"},
        {"apply": True, "method": "truncate",  "threshold": 0.01, "symmetric": "both"},
        {"apply": True, "method": "winsorize", "threshold": 0.05, "symmetric": "both"},
        {"apply": True, "method": "truncate",  "threshold": 0.05, "symmetric": "both"},
    ])
    dep_transform: list[str] = field(default_factory=lambda: ["none"])
    ind_na_treatment: list[dict] = field(default_factory=lambda: [{"method": "omit"}])
    ind_outlier: list[dict] = field(default_factory=lambda: [
        {"apply": False},
        {"apply": True, "method": "winsorize", "threshold": 0.01, "symmetric": "both"},
        {"apply": True, "method": "truncate",  "threshold": 0.01, "symmetric": "both"},
        {"apply": True, "method": "winsorize", "threshold": 0.05, "symmetric": "both"},
        {"apply": True, "method": "truncate",  "threshold": 0.05, "symmetric": "both"},
    ])
    ind_transform: list[str] = field(default_factory=lambda: ["none", "zscore", "mean_center"])
    fixed_effects: list[dict] = field(default_factory=lambda: [
        {"time": None,      "country": False, "fe_method": "dummy"},
        {"time": None,      "country": True,  "fe_method": "dummy"},
        {"time": "year",    "country": True,  "fe_method": "dummy"},
        {"time": "year",    "country": False, "fe_method": "dummy"},
        {"time": "quarter", "country": False, "fe_method": "dummy"},
        {"time": "quarter", "country": True,  "fe_method": "dummy"},
        {"time": "month",   "country": False, "fe_method": "dummy"},
        {"time": "month",   "country": True,  "fe_method": "dummy"},
    ])
    models: list[str] = field(default_factory=lambda: ["OLS", "RLM"])


@dataclass
class ConstraintsConfig:
    min_obs: int = 100
    country_dummy_cap: int = 50
    country_dummy_keep: int = 30


@dataclass
class RunConfig:
    mode: str = "sample"          # sample | full
    sample_size: int = 20000
    seed: int = 42
    max_workers: Optional[int] = None


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------

@dataclass
class Config:
    dataset: DatasetConfig
    roles: RolesConfig
    variable_selection: VariableSelectionConfig = field(default_factory=VariableSelectionConfig)
    design_space: DesignSpaceConfig = field(default_factory=DesignSpaceConfig)
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    run: RunConfig = field(default_factory=RunConfig)
    focal_coefficients: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # (De)serialization
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        ds = d.get("dataset", {})
        roles = d.get("roles", {})
        vs = d.get("variable_selection", {})
        dsp = d.get("design_space", {})
        con = d.get("constraints", {})
        run = d.get("run", {})

        return cls(
            dataset=DatasetConfig(**ds),
            roles=RolesConfig(
                dependent=roles["dependent"],
                independent=roles.get("independent", []),
                time_var=roles.get("time_var"),
                country_var=roles.get("country_var"),
                instruments=roles.get("instruments", []),
            ),
            variable_selection=VariableSelectionConfig(
                min_variables=vs.get("min_variables", 8),
                max_correlation=vs.get("max_correlation", 0.7),
                required_vars=vs.get("required_vars", []),
                target_combinations=vs.get("target_combinations", 3000),
                precomputed_combos_path=vs.get("precomputed_combos_path"),
            ),
            design_space=DesignSpaceConfig(
                dep_na_treatment=dsp.get("dep_na_treatment", ["omit", "zero"]),
                dep_outlier=dsp.get("dep_outlier", DesignSpaceConfig().dep_outlier),
                dep_transform=dsp.get("dep_transform", ["none"]),
                ind_na_treatment=dsp.get("ind_na_treatment", [{"method": "omit"}]),
                ind_outlier=dsp.get("ind_outlier", DesignSpaceConfig().ind_outlier),
                ind_transform=dsp.get("ind_transform", ["none", "zscore", "mean_center"]),
                fixed_effects=dsp.get("fixed_effects", DesignSpaceConfig().fixed_effects),
                models=dsp.get("models", ["OLS", "RLM"]),
            ),
            constraints=ConstraintsConfig(
                min_obs=con.get("min_obs", 100),
                country_dummy_cap=con.get("country_dummy_cap", 50),
                country_dummy_keep=con.get("country_dummy_keep", 30),
            ),
            run=RunConfig(
                mode=run.get("mode", "sample"),
                sample_size=run.get("sample_size", 20000),
                seed=run.get("seed", 42),
                max_workers=run.get("max_workers"),
            ),
            focal_coefficients=d.get("focal_coefficients", []),
        )

    @classmethod
    def from_json(cls, path: str) -> "Config":
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def to_dict(self) -> dict:
        import dataclasses
        def _convert(obj: Any) -> Any:
            if dataclasses.is_dataclass(obj):
                return {k: _convert(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, list):
                return [_convert(i) for i in obj]
            return obj
        return _convert(self)

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, columns: Optional[list[str]] = None) -> None:
        """Raise ConfigValidationError if the config is inconsistent.

        Pass ``columns`` (list of column names from the dataset) to enable
        column-existence checks.
        """
        errors: list[str] = []

        if columns is not None:
            col_set = set(columns)
            if self.roles.dependent not in col_set:
                errors.append(f"dependent variable '{self.roles.dependent}' not in dataset")
            missing_ind = [v for v in self.roles.independent if v not in col_set]
            if missing_ind:
                errors.append(f"independent variables not in dataset: {missing_ind}")
            if self.roles.time_var and self.roles.time_var not in col_set:
                errors.append(f"time_var '{self.roles.time_var}' not in dataset")
            if self.roles.country_var and self.roles.country_var not in col_set:
                errors.append(f"country_var '{self.roles.country_var}' not in dataset")
            missing_req = [v for v in self.variable_selection.required_vars if v not in col_set]
            if missing_req:
                errors.append(f"required_vars not in dataset: {missing_req}")

        if self.variable_selection.max_correlation <= 0 or self.variable_selection.max_correlation >= 1:
            errors.append("max_correlation must be in (0, 1)")
        if self.variable_selection.min_variables < 1:
            errors.append("min_variables must be >= 1")
        if self.constraints.min_obs < 1:
            errors.append("min_obs must be >= 1")
        if self.run.mode not in ("sample", "full"):
            errors.append("run.mode must be 'sample' or 'full'")
        if self.run.sample_size < 1:
            errors.append("run.sample_size must be >= 1")

        valid_models = {"OLS", "RLM", "2SLS", "Hurdle"}
        bad = [m for m in self.design_space.models if m not in valid_models]
        if bad:
            errors.append(f"unknown model types: {bad}")

        if "2SLS" in self.design_space.models and not self.roles.instruments:
            errors.append("2SLS requires at least one instrument in roles.instruments")

        if self.dataset.format not in ("csv", "xlsx"):
            errors.append("dataset.format must be 'csv' or 'xlsx'")

        if errors:
            raise ConfigValidationError(errors)


# ---------------------------------------------------------------------------
# n_specs formula (§7)
# ---------------------------------------------------------------------------

def compute_n_specs(config: Config, n_var_combos: int) -> int:
    """Compute the total (uncapped) number of specifications."""
    ds = config.design_space
    model_weight = sum(3 if m == "2SLS" else 1 for m in ds.models)
    return (
        n_var_combos
        * len(ds.dep_na_treatment)
        * len(ds.dep_outlier)
        * len(ds.dep_transform)
        * len(ds.ind_na_treatment)
        * len(ds.ind_outlier)
        * len(ds.ind_transform)
        * len(ds.fixed_effects)
        * model_weight
    )
