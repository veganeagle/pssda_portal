"""Shared sub-title breakdown: within a Title_Norm group, which raw JobTitleNorm
variants are large enough to name individually, vs. folded into "Other".

Exists because Title_Norm has to be the cross-employer comparable unit (many
employers don't share a finer split — see SUNSHINE.md-adjacent finding: TDSB's
"Teacher" Title_Norm merges Elementary + Secondary + a few others), so we can't
just switch the grouping key finer without breaking domains like university
titles, which fragment into hundreds of near-unique raw strings. Instead: keep
Title_Norm as the key, but never silently label the group with one arbitrarily
picked variant — show what's actually inside it, or nothing if it's genuinely
fragmented (no variant clears the threshold).
"""
import pandas as pd

MIN_SHARE = 0.10
MIN_COUNT = 5


def compute_title_breakdown(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """One row per (group_cols..., variant, headcount, avg_salary, median_salary).
    variant is a real JobTitleNorm string when it's >=MIN_SHARE of its group and
    >=MIN_COUNT people, otherwise all such rows are folded into "Other" (computed
    from the real rows, not an average-of-averages)."""
    key = group_cols + ["JobTitleNorm"]
    variant_counts = df.groupby(key)["EmployeeID"].size().rename("headcount").reset_index()
    group_total = variant_counts.groupby(group_cols)["headcount"].transform("sum")
    variant_counts["named"] = (
        (variant_counts["headcount"] / group_total >= MIN_SHARE) & (variant_counts["headcount"] >= MIN_COUNT)
    )

    tagged = df.merge(variant_counts[key + ["named"]], on=key, how="left")
    tagged["variant"] = tagged["JobTitleNorm"].where(tagged["named"], "Other")

    out_key = group_cols + ["variant"]
    out = tagged.groupby(out_key).agg(
        headcount=("EmployeeID", "size"),
        avg_salary=("SalaryPaid", "mean"),
        median_salary=("SalaryPaid", "median"),
    ).reset_index()
    out["avg_salary"] = out["avg_salary"].round(0)
    out["median_salary"] = out["median_salary"].round(0)

    # "Other" last regardless of its size — it's a residual bucket, not a rank.
    out["_other_last"] = out["variant"] == "Other"
    out = out.sort_values(group_cols + ["_other_last", "headcount"], ascending=[True] * len(group_cols) + [True, False])
    return out.drop(columns="_other_last").reset_index(drop=True)
