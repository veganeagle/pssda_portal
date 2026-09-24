"""Shared aggregate gender-composition helper. Never applied at the individual
level (see models/employee_profile.py's prob_female field, hidden in the UI) —
only as a group statistic, and only when the group is large enough that a
name-based estimate averaged over it means something.
"""
import pandas as pd

MIN_GROUP_SIZE = 20


def compute_pct_female(df: pd.DataFrame, key: list[str]) -> pd.DataFrame:
    """df must already have a Prob_Female column merged in (from
    employees_enriched). Returns one row per group: key columns, n, pct_female
    (0-100, None when n < MIN_GROUP_SIZE)."""
    g = df.groupby(key)
    out = g.agg(n=("Prob_Female", "size"), pct_female=("Prob_Female", lambda s: (s >= 0.5).mean() * 100))
    out["pct_female"] = out["pct_female"].round(1).where(out["n"] >= MIN_GROUP_SIZE)
    return out.reset_index()
