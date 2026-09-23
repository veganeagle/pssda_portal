"""Builds the employee_profile cube: three flat parquet tables in data/profiles/,
keyed by employee_id. Nesting into models.employee_profile.EmployeeProfile happens
in `access` per-request, not here.

Dev-time script: `python -m pipeline.cubes.employee_profile` for a full build, or
import build_employee_profile_cube(employee_ids=[...]) to scope a run. Paybands are
always computed against the full population regardless of employee_ids.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from pipeline.manifest import update_manifest

SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles"))

MIN_PEER_GROUP_SIZE = 3  # below this a percentile is "100th of 1" noise, not signal

PEER_GROUP_TIERS = [
    ("employer", ["EmployerID"], lambda r: r["EmployerName"]),
    ("employer_title", ["EmployerID", "Title_Norm"], lambda r: f"{r['EmployerName']} — {r['Title_Norm']}"),
    ("sector_title", ["SectorID", "Title_Norm"], lambda r: f"{r['SectorName']} — {r['Title_Norm']}"),
]


def load_source() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    history = pd.read_parquet(os.path.join(SOURCE_DIR, "employment_history_enriched.parquet"))
    employees = pd.read_parquet(os.path.join(SOURCE_DIR, "employees_enriched.parquet"))
    sectors = pd.read_parquet(os.path.join(SOURCE_DIR, "sectors_canonical.parquet"))
    return history, employees, sectors


def compute_payband_standings(history: pd.DataFrame) -> pd.DataFrame:
    """One row per (employee, year, peer_group), computed against the full peer
    population regardless of which employees end up in the final output.
    Expects history to already carry a SectorName column."""
    base = history[history["Title_Norm"].notna()].copy()

    tiers = []
    for peer_group, group_cols, label_fn in PEER_GROUP_TIERS:
        key = ["Year"] + group_cols
        t = base.copy()
        t["n_peers"] = t.groupby(key)["TotalComp"].transform("size")
        t = t[t["n_peers"] >= MIN_PEER_GROUP_SIZE].copy()
        t["rank"] = t.groupby(key)["TotalComp"].rank(method="dense", ascending=False).astype(int)
        t["percentile"] = (t.groupby(key)["TotalComp"].rank(pct=True) * 100).round(1)
        t["peer_group"] = peer_group
        t["peer_group_label"] = t.apply(label_fn, axis=1)
        tiers.append(t[["EmployeeID", "Year", "peer_group", "peer_group_label", "n_peers", "rank", "percentile"]])

    out = pd.concat(tiers, ignore_index=True)
    return out.rename(columns={"EmployeeID": "employee_id", "Year": "year"})


def build_history_table(history: pd.DataFrame, employee_ids: list[str] | None = None) -> pd.DataFrame:
    df = history if employee_ids is None else history[history["EmployeeID"].isin(employee_ids)]

    # GapFlag is 0 even on a true first appearance (it only flags a return after an
    # absence) — also require TenureOnList > 1, or the YoY 0.0 sentinel reads as a
    # real "no raise" on someone's first year. See SUNSHINE.md #1/#2.
    comparable = (df["GapFlag"] == 0) & (df["TenureOnList"] > 1)

    out = pd.DataFrame({
        "employee_id": df["EmployeeID"],
        "year": df["Year"].astype(int),
        "employer_id": df["EmployerID"],
        "employer_name": df["EmployerName"],
        "sector_id": df["SectorID"],
        "sector_name": df["SectorName"],
        "job_title": df["JobTitleNorm"],
        "title_norm": df["Title_Norm"],
        "salary_paid": df["SalaryPaid"],
        "taxable_benefits": df["TaxableBenefits"],
        "total_comp": df["TotalComp"],
        "yoy_salary_increase": df["YoYSalaryIncrease"].where(comparable),
        "yoy_total_comp_increase": df["YoYTotalCompIncrease"].where(comparable),
        "comparable_to_prior_year": comparable,
        "gap_flag": df["GapFlag"].astype(bool),
        "employer_switch_flag": df["EmployerSwitchFlag"].astype(bool),
        "promotion_flag": df["PromotionFlag"].astype(bool),
    })
    return out.sort_values(["employee_id", "year"]).reset_index(drop=True)


def build_wide_table(
    history: pd.DataFrame, employees: pd.DataFrame, dataset_min_year: int,
    employee_ids: list[str] | None = None,
) -> pd.DataFrame:
    emp = employees if employee_ids is None else employees[employees["EmployeeID"].isin(employee_ids)]

    years_disclosed = history.groupby("EmployeeID").size().rename("years_disclosed")
    emp = emp.merge(years_disclosed, left_on="EmployeeID", right_index=True, how="left")
    emp["years_disclosed"] = emp["years_disclosed"].fillna(0).astype(int)

    # "Current" = most recently disclosed year, which may not be the dataset's latest.
    idx = history.groupby("EmployeeID")["Year"].idxmax()
    current = history.loc[idx].set_index("EmployeeID")

    def cur(col):
        return emp["EmployeeID"].map(current[col])

    out = pd.DataFrame({
        "employee_id": emp["EmployeeID"],
        "first_name": emp["FirstName"],
        "last_name": emp["LastName"],
        "middle": emp["Middle"],
        "first_initial": emp["FirstInitial"],
        "first_seen_year": emp["FirstSeenYear"].astype(int),
        "first_seen_year_left_censored": emp["FirstSeenYear"].astype(int) == dataset_min_year,
        "last_seen_year": emp["LastActiveYear"].astype(int),
        "years_disclosed": emp["years_disclosed"],
        "prob_female": emp["Prob_Female"],
        "current_year": cur("Year").astype(int),
        "current_employer_id": cur("EmployerID"),
        "current_employer_name": cur("EmployerName"),
        "current_sector_id": cur("SectorID"),
        "current_sector_name": cur("SectorName"),
        "current_subsector": cur("SubSector"),
        "current_job_title": cur("JobTitleNorm"),
        "current_title_norm": cur("Title_Norm"),
        "current_region": cur("Region"),
        "current_municipality": cur("Municipality"),
        "current_salary_paid": cur("SalaryPaid"),
        "current_taxable_benefits": cur("TaxableBenefits"),
        "current_total_comp": cur("TotalComp"),
    })
    return out.reset_index(drop=True)


def write_sector_lookup(sectors: pd.DataFrame) -> None:
    out = pd.DataFrame({
        "sector_id": sectors["sector_id"].astype(str),
        "sector_name": sectors["canonical"],
    }).sort_values("sector_name")
    out.to_parquet(os.path.join(OUTPUT_DIR, "sectors.parquet"), index=False)


def write_tables(wide: pd.DataFrame, history_out: pd.DataFrame, payband_out: pd.DataFrame, mode: str) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    wide.to_parquet(os.path.join(OUTPUT_DIR, "employee_wide.parquet"), index=False)
    history_out.to_parquet(os.path.join(OUTPUT_DIR, "employee_history.parquet"), index=False)
    payband_out.to_parquet(os.path.join(OUTPUT_DIR, "employee_payband_standing.parquet"), index=False)

    return update_manifest("employee_profile", {
        "mode": mode,
        "employee_wide.parquet": len(wide),
        "employee_history.parquet": len(history_out),
        "employee_payband_standing.parquet": len(payband_out),
    })


def build_employee_profile_cube(employee_ids: list[str] | None = None) -> dict:
    history, employees, sectors = load_source()
    dataset_min_year = int(history["Year"].min())
    sector_name_map = dict(zip(sectors["sector_id"].astype(str), sectors["canonical"]))
    history = history.copy()
    history["SectorName"] = history["SectorID"].astype(str).map(sector_name_map)

    payband_all = compute_payband_standings(history)  # full population, always
    wide = build_wide_table(history, employees, dataset_min_year, employee_ids)
    history_out = build_history_table(history, employee_ids)
    payband_out = payband_all if employee_ids is None else payband_all[payband_all["employee_id"].isin(employee_ids)]
    write_sector_lookup(sectors)  # small reference table, always written in full

    return write_tables(wide, history_out, payband_out, mode="full" if employee_ids is None else "test")


def _pick_test_employee_ids(history: pd.DataFrame, n_each: int = 1) -> list[str]:
    """A small varied set — normalized title, a gap year, an employer switch, and an
    unnormalized title — so a test run exercises every code path."""
    has_title = history[history["Title_Norm"].notna()]
    has_gap = history[history["GapFlag"] == 1]
    has_switch = history[history["EmployerSwitchFlag"] == 1]
    no_title_ids = set(history[history["Title_Norm"].isna()]["EmployeeID"]) - set(has_title["EmployeeID"])

    ids = (
        has_title["EmployeeID"].drop_duplicates().head(n_each).tolist()
        + has_gap["EmployeeID"].drop_duplicates().head(n_each).tolist()
        + has_switch["EmployeeID"].drop_duplicates().head(n_each).tolist()
        + list(no_title_ids)[:n_each]
    )
    return list(dict.fromkeys(ids))  # de-dup, preserve order


if __name__ == "__main__":
    import sys

    if "--full" in sys.argv:
        print(json.dumps(build_employee_profile_cube(), indent=2))
    else:
        history_df, _, _ = load_source()
        test_ids = _pick_test_employee_ids(history_df)
        print(f"Test run for {len(test_ids)} employee_ids: {test_ids}")
        print(json.dumps(build_employee_profile_cube(employee_ids=test_ids), indent=2))
