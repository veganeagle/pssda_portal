"""Shared DuckDB-result-to-dict cleanup, used by every access/*_profile.py module."""
import math

import pandas as pd


def _none_if_nan(value):
    # DuckDB NULLs surface as NaN for numeric columns; NaN isn't valid JSON and
    # breaks JSON.parse in the browser, so normalize before it reaches a model.
    return None if isinstance(value, float) and math.isnan(value) else value


def records(df: pd.DataFrame, exclude: tuple[str, ...] = ()) -> list[dict]:
    return [{k: _none_if_nan(v) for k, v in row.items() if k not in exclude} for row in df.to_dict(orient="records")]
