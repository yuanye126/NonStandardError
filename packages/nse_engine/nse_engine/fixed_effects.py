"""
Fixed-effects preprocessing: create time and country dummy columns.
Returns a modified DataFrame and the list of dummy column names added.
"""
from __future__ import annotations

import pandas as pd


def _top_n_dummies(
    df: pd.DataFrame,
    col: str,
    cap: int,
    keep: int,
    prefix: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Create dummies for the top-N most frequent categories, collapsing the rest."""
    vc = df[col].value_counts()
    if len(vc) > cap:
        top = vc.iloc[:keep].index.tolist()
        collapsed = df[col].where(df[col].isin(top), other="__other__")
    else:
        collapsed = df[col]
    dummies = pd.get_dummies(collapsed, prefix=prefix, drop_first=True)
    dummies = dummies.astype(float)
    return dummies, list(dummies.columns)


def add_fixed_effects(
    df: pd.DataFrame,
    fe_spec: dict,
    time_col: str | None,
    country_col: str | None,
    country_dummy_cap: int = 50,
    country_dummy_keep: int = 30,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Add fixed-effect dummy columns to df.

    fe_spec: {"time": None | "year" | "quarter" | "month",
              "country": bool, "fe_method": "dummy"}

    Returns (df_with_fe, fe_column_names).
    """
    df = df.copy()
    fe_cols: list[str] = []

    time_granularity = fe_spec.get("time")
    use_country = fe_spec.get("country", False)

    if time_granularity and time_col:
        dt = pd.to_datetime(df[time_col], errors="coerce")
        if time_granularity == "year":
            period = dt.dt.year.astype("Int64").astype(str)
        elif time_granularity == "quarter":
            period = dt.dt.to_period("Q").astype(str)
        elif time_granularity == "month":
            period = dt.dt.to_period("M").astype(str)
        else:
            period = None

        if period is not None:
            dummies = pd.get_dummies(period, prefix=f"fe_time_{time_granularity}", drop_first=True)
            dummies = dummies.astype(float)
            df = pd.concat([df, dummies], axis=1)
            fe_cols.extend(dummies.columns.tolist())

    if use_country and country_col:
        dummies, cols = _top_n_dummies(
            df, country_col, country_dummy_cap, country_dummy_keep, prefix="fe_country"
        )
        df = pd.concat([df, dummies], axis=1)
        fe_cols.extend(cols)

    return df, fe_cols
