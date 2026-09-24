"""Shared matched-cohort comparability helper — SUNSHINE.md #2: a same-incumbent
average, not a same-role year-over-year average of two different populations.
Used wherever a "raise" is computed for a group (position, employer+position).
"""
import pandas as pd


def matched_cohort_flag(history: pd.DataFrame, position_cols: list[str]) -> pd.Series:
    """True where this row is comparable to a prior-year record (GapFlag==0,
    TenureOnList>1) AND that prior record was the same position — defined by
    position_cols, e.g. ["SectorID", "Title_Norm"] or ["SectorID", "Title_Norm",
    "EmployerID"] — not just the same employee."""
    prior_cols = ["EmployeeID", "Year"] + position_cols
    prior = history[prior_cols].copy()
    prior["Year"] = prior["Year"] + 1
    rename = {c: f"Prior{c}" for c in position_cols}
    prior = prior.rename(columns=rename)

    merged = history[["EmployeeID", "Year", "GapFlag", "TenureOnList"] + position_cols].merge(
        prior, on=["EmployeeID", "Year"], how="left"
    )
    same_position = pd.Series(True, index=merged.index)
    for c in position_cols:
        same_position &= merged[c] == merged[f"Prior{c}"]

    return ((merged["GapFlag"] == 0) & (merged["TenureOnList"] > 1) & same_position).values
