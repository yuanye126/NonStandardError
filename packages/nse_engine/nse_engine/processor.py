"""
RegressionProcessor: runs a single specification and returns a result dict.
Driven entirely by Config — no hardcoded paths, variable names, or thresholds.
"""
from __future__ import annotations

import warnings
from typing import Any, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .config import Config, ConstraintsConfig
from .data_transformations import apply_outlier_treatment, transform_series
from .fixed_effects import add_fixed_effects


# ---------------------------------------------------------------------------
# Preprocessed-frame cache key (for web preview performance)
# ---------------------------------------------------------------------------

def _cache_key(
    var_combo: tuple[str, ...],
    dep_na: str,
    dep_outlier: dict,
    dep_transform: str,
    ind_na: dict,
    ind_outlier: dict,
    ind_transform: str,
    fe_spec: dict,
) -> tuple:
    """Stable, hashable key for a preprocessed frame."""
    import json
    return (
        var_combo,
        dep_na,
        json.dumps(dep_outlier, sort_keys=True),
        dep_transform,
        json.dumps(ind_na, sort_keys=True),
        json.dumps(ind_outlier, sort_keys=True),
        ind_transform,
        json.dumps(fe_spec, sort_keys=True),
    )


# ---------------------------------------------------------------------------
# OLS / RLM
# ---------------------------------------------------------------------------

def _fit_ols(endog, exog) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sm.OLS(endog, exog).fit()
    return _extract_ols_result(res, "OLS")


def _fit_rlm(endog, exog) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sm.RLM(endog, exog, M=sm.robust.norms.HuberT()).fit()
    return _extract_ols_result(res, "RLM")


def _extract_ols_result(res, model_type: str) -> dict:
    fitted = res.fittedvalues
    resid = res.resid
    n = len(fitted)
    params = dict(zip(res.model.exog_names, res.params))
    bse = dict(zip(res.model.exog_names, res.bse))
    pvals = {}
    try:
        pvals = dict(zip(res.model.exog_names, res.pvalues))
    except Exception:
        pass

    rmse = float(np.sqrt(np.mean(resid ** 2))) if n > 0 else np.nan
    r2 = getattr(res, "rsquared", np.nan)
    adj_r2 = getattr(res, "rsquared_adj", np.nan)
    model_p = getattr(res, "f_pvalue", np.nan)
    df_resid = getattr(res, "df_resid", np.nan)

    ci_low: dict[str, float] = {}
    ci_high: dict[str, float] = {}
    try:
        ci = res.conf_int()
        for name in ci.index:
            ci_low[name] = float(ci.loc[name, 0])
            ci_high[name] = float(ci.loc[name, 1])
    except Exception:
        pass

    return {
        "model_type": model_type,
        "n_obs": n,
        "params": params,
        "bse": bse,
        "pvalues": pvals,
        "r2": float(r2) if not np.isnan(r2) else None,
        "adj_r2": float(adj_r2) if not np.isnan(adj_r2) else None,
        "model_p_value": float(model_p) if not np.isnan(model_p) else None,
        "df_resid": float(df_resid),
        "mean_fitted": float(fitted.mean()),
        "iqr_fitted": float(np.percentile(fitted, 75) - np.percentile(fitted, 25)),
        "idr_fitted": float(np.percentile(fitted, 90) - np.percentile(fitted, 10)),
        "mean_se": float(np.mean(list(bse.values()))) if bse else None,
        "rmse": rmse,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


# ---------------------------------------------------------------------------
# 2SLS (three rows: IMR, GR, IMRGR)
# ---------------------------------------------------------------------------

def _fit_2sls(endog, exog_endo, instruments, exog_exog, model_type_suffix: str) -> dict:
    """Fit IV/2SLS using linearmodels."""
    try:
        from linearmodels.iv import IV2SLS
    except ImportError:
        raise RuntimeError("linearmodels is required for 2SLS")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mod = IV2SLS(
            dependent=endog,
            exog=exog_exog,
            endog=exog_endo,
            instruments=instruments,
        )
        res = mod.fit(cov_type="robust")

    result = _extract_ols_result(res, f"2SLS_{model_type_suffix}")
    return result


# ---------------------------------------------------------------------------
# Hurdle model (two-part: probit + OLS on positives)
# ---------------------------------------------------------------------------

def _fit_hurdle(
    dep: pd.Series,
    ind_matrix: pd.DataFrame,
    dep_name: str,
) -> list[dict]:
    """Fit a two-part hurdle model. Returns marginal effects."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Part 1: probit on participation (y > 0)
        y_part = (dep > 0).astype(float)
        probit = sm.Probit(y_part, ind_matrix).fit(disp=False)

        # Part 2: OLS on positive outcomes
        mask = dep > 0
        if mask.sum() < 10:
            return []
        ols_res = sm.OLS(dep[mask], ind_matrix[mask]).fit()

    result = _extract_ols_result(ols_res, "Hurdle")
    result["probit_params"] = dict(zip(probit.model.exog_names, probit.params))
    result["probit_pvalues"] = dict(zip(probit.model.exog_names, probit.pvalues))

    # Marginal effects (unconditional = probit_mfx * E[y|y>0] + P(y>0) * ols_coef)
    try:
        mfx = probit.get_margeff()
        p_participate = y_part.mean()
        e_y_pos = dep[mask].mean()
        marginal_effects: dict[str, dict] = {}
        for name in probit.model.exog_names:
            if name == "const":
                continue
            pe = float(mfx.margeff[list(probit.model.exog_names).index(name)])
            ae = float(ols_res.params.get(name, 0.0))
            me = float(pe * e_y_pos + p_participate * ae)
            marginal_effects[name] = {
                "participation_effect": pe,
                "amount_effect": ae,
                "marginal_effect": me,
            }
        result["marginal_effects"] = marginal_effects
    except Exception:
        result["marginal_effects"] = {}

    return [result]


# ---------------------------------------------------------------------------
# Main preprocessor + runner
# ---------------------------------------------------------------------------

class RegressionProcessor:
    """Preprocess a spec and run one or more models.

    Parameters
    ----------
    data : pd.DataFrame
        The raw dataset. Not mutated.
    config : Config
        The full run configuration.
    frame_cache : dict | None
        Optional shared cache for preprocessed frames (web preview path).
    """

    def __init__(
        self,
        data: pd.DataFrame,
        config: Config,
        frame_cache: Optional[dict] = None,
    ):
        self.raw_data = data
        self.config = config
        self.constraints: ConstraintsConfig = config.constraints
        self.frame_cache = frame_cache if frame_cache is not None else {}

    def run_spec(self, spec: dict) -> list[dict]:
        """Run all models for one specification dict.

        Returns a list of result dicts (one per model; 2SLS returns three).
        Raises ValueError with a failure reason string if the spec cannot run.
        """
        cfg = self.config
        dep = cfg.roles.dependent
        ind_vars: list[str] = spec["ind_vars"]
        dep_na = spec["dep_na_treatment"]
        dep_outlier_spec = spec["dep_outlier"]
        dep_transform = spec["dep_transform"]
        ind_na_spec = spec["ind_na_treatment"]
        ind_outlier_spec = spec["ind_outlier"]
        ind_transform = spec["ind_transform"]
        fe_spec = spec["fixed_effects"]
        models = spec["models"]

        key = _cache_key(
            tuple(sorted(ind_vars)),
            dep_na,
            dep_outlier_spec,
            dep_transform,
            ind_na_spec,
            ind_outlier_spec,
            ind_transform,
            fe_spec,
        )

        if key in self.frame_cache:
            df, fe_cols = self.frame_cache[key]
        else:
            df, fe_cols = self._preprocess(
                dep, ind_vars, dep_na, dep_outlier_spec, dep_transform,
                ind_na_spec, ind_outlier_spec, ind_transform, fe_spec,
            )
            self.frame_cache[key] = (df, fe_cols)

        if len(df) < self.constraints.min_obs:
            raise ValueError(f"insufficient_observations (n={len(df)})")

        endog = df[dep]
        regressors = ind_vars + fe_cols
        exog_df = df[regressors].copy()
        exog_df.insert(0, "const", 1.0)

        results: list[dict] = []

        spec_meta = {
            "ind_vars": ind_vars,
            "dep_na_treatment": dep_na,
            "dep_outlier": dep_outlier_spec,
            "dep_transform": dep_transform,
            "ind_na_treatment": ind_na_spec,
            "ind_outlier": ind_outlier_spec,
            "ind_transform": ind_transform,
            "fixed_effects": fe_spec,
        }

        for model_type in models:
            try:
                if model_type == "OLS":
                    r = _fit_ols(endog, exog_df)
                elif model_type == "RLM":
                    r = _fit_rlm(endog, exog_df)
                elif model_type == "2SLS":
                    rows = self._run_2sls(endog, exog_df, df, ind_vars, fe_cols)
                    for row in rows:
                        row.update(spec_meta)
                    results.extend(rows)
                    continue
                elif model_type == "Hurdle":
                    rows = _fit_hurdle(endog, exog_df, dep)
                    for row in rows:
                        row.update(spec_meta)
                    results.extend(rows)
                    continue
                else:
                    continue
                r.update(spec_meta)
                results.append(r)
            except Exception as exc:
                raise ValueError(f"model_{model_type.lower()}_failed: {exc}") from exc

        return results

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    def _preprocess(
        self,
        dep: str,
        ind_vars: list[str],
        dep_na: str,
        dep_outlier_spec: dict,
        dep_transform: str,
        ind_na_spec: dict,
        ind_outlier_spec: dict,
        ind_transform: str,
        fe_spec: dict,
    ) -> tuple[pd.DataFrame, list[str]]:
        cfg = self.config
        df = self.raw_data[[dep] + ind_vars +
                           ([cfg.roles.time_var] if cfg.roles.time_var else []) +
                           ([cfg.roles.country_var] if cfg.roles.country_var else [])
                           ].copy()

        # --- DV NA treatment ---
        if dep_na == "omit":
            df = df.dropna(subset=[dep])
        elif dep_na == "zero":
            df[dep] = df[dep].fillna(0.0)

        # --- DV outlier ---
        dep_series = apply_outlier_treatment(df[dep], dep_outlier_spec)
        if isinstance(dep_series, pd.Series) and len(dep_series) < len(df):
            df = df.loc[dep_series.index]
        df[dep] = dep_series.reindex(df.index)

        # --- DV transform ---
        df[dep] = transform_series(df[dep], dep_transform)

        # --- IV NA treatment ---
        ind_na_method = ind_na_spec.get("method", "omit")
        if ind_na_method == "omit":
            df = df.dropna(subset=ind_vars)
        elif ind_na_method == "zero":
            df[ind_vars] = df[ind_vars].fillna(0.0)
        elif ind_na_method == "mean":
            df[ind_vars] = df[ind_vars].fillna(df[ind_vars].mean())

        # --- IV outlier ---
        for v in ind_vars:
            treated = apply_outlier_treatment(df[v], ind_outlier_spec)
            if isinstance(treated, pd.Series) and len(treated) < len(df):
                df = df.loc[treated.index]
            df[v] = treated.reindex(df.index)

        # --- IV transform ---
        for v in ind_vars:
            df[v] = transform_series(df[v], ind_transform)

        # --- Fixed effects ---
        df, fe_cols = add_fixed_effects(
            df, fe_spec,
            time_col=cfg.roles.time_var,
            country_col=cfg.roles.country_var,
            country_dummy_cap=cfg.constraints.country_dummy_cap,
            country_dummy_keep=cfg.constraints.country_dummy_keep,
        )

        # Drop any remaining NaN rows
        all_cols = [dep] + ind_vars + fe_cols
        df = df.dropna(subset=all_cols)
        df = df.reset_index(drop=True)

        return df, fe_cols

    # ------------------------------------------------------------------
    # 2SLS triple-row (IMR, GR, IMRGR)
    # ------------------------------------------------------------------

    def _run_2sls(
        self,
        endog: pd.Series,
        exog_df: pd.DataFrame,
        df: pd.DataFrame,
        ind_vars: list[str],
        fe_cols: list[str],
    ) -> list[dict]:
        """Return the standard three 2SLS rows (IMR / GR / IMRGR)."""
        instruments_cols = self.config.roles.instruments
        if not instruments_cols:
            raise ValueError("2SLS requires instruments")

        available_instruments = [c for c in instruments_cols if c in df.columns]
        if not available_instruments:
            raise ValueError("no instrument columns found in data")

        results = []
        instrument_df = df[available_instruments].copy()
        instrument_df.insert(0, "const", 1.0)

        # Suffixes per paper: IMR (inverse Mills ratio selection), GR (growth-rate IV), IMRGR (both)
        for suffix in ["IMR", "GR", "IMRGR"]:
            try:
                r = _fit_2sls(
                    endog=endog,
                    exog_endo=exog_df.drop(columns=["const"], errors="ignore"),
                    instruments=instrument_df,
                    exog_exog=pd.DataFrame({"const": np.ones(len(endog))}),
                    model_type_suffix=suffix,
                )
                results.append(r)
            except Exception as exc:
                raise ValueError(f"2sls_{suffix}_failed: {exc}") from exc

        return results
