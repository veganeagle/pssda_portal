"""Builds the employer_position_profile ("combo") cube: the intersection of one
employer and one position (sector, title_norm) — e.g. "Teacher at TDSB". Reached
only as a second step from an employer or position page (see web_app), never
searched or browsed directly.

Same matched-cohort raise, gender-suppression, and Title_Norm-vs-JobTitleNorm
breakdown rules as position_profile.py and employer_profile.py — this cube is
the same computation, one dimension finer.

Dev-time script: `python -m pipeline.cubes.employer_position_profile`.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from pipeline.gender import compute_pct_female
from pipeline.manifest import update_manifest
from pipeline.matched_cohort import matched_cohort_flag
from pipeline.title_breakdown import compute_title_breakdown

SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles"))

# A combo needs at least this many people in its own most recent year to get a
# page at all — same rationale as position_by_employer's threshold.
MIN_GROUP_SIZE = 3


def load_source() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    history = pd.read_parquet(os.path.join(SOURCE_DIR, "employment_history_enriched.parquet"))
    employees = pd.read_parquet(os.path.join(SOURCE_DIR, "employees_enriched.parquet"))
    sectors = pd.read_parquet(os.path.join(SOURCE_DIR, "sectors_canonical.parquet"))
    return history, employees, sectors


def build_combo_history(history: pd.DataFrame, employees: pd.DataFrame) -> pd.DataFrame:
    base = history[history["Title_Norm"].notna()].copy()
    base["MatchedCohort"] = matched_cohort_flag(base, ["SectorID", "Title_Norm", "EmployerID"])
    base = base.merge(employees[["EmployeeID", "Prob_Female"]], on="EmployeeID", how="left")

    key = ["EmployerID", "SectorID", "Title_Norm", "Year"]
    headcount = base.groupby(key)["EmployeeID"].size().rename("headcount")
    avg_salary = base.groupby(key)["SalaryPaid"].mean().round(0).rename("avg_salary")
    median_salary = base.groupby(key)["SalaryPaid"].median().round(0).rename("median_salary")
    p90_salary = base.groupby(key)["SalaryPaid"].quantile(0.9).round(0).rename("p90_salary")
    max_salary = base.groupby(key)["SalaryPaid"].max().round(0).rename("max_salary")
    avg_total_comp = base.groupby(key)["TotalComp"].mean().round(0).rename("avg_total_comp")

    matched = base[base["MatchedCohort"]]
    avg_raise_matched = matched.groupby(key)["YoYSalaryIncrease"].mean().round(4).rename("avg_raise_matched")
    cohort_n = matched.groupby(key)["EmployeeID"].size().rename("cohort_n")

    gender = compute_pct_female(base, key).set_index(key)["pct_female"].rename("pct_female")

    out = pd.concat(
        [headcount, avg_salary, median_salary, p90_salary, max_salary, avg_total_comp,
         avg_raise_matched, cohort_n, gender], axis=1
    ).reset_index()
    out["cohort_n"] = out["cohort_n"].fillna(0).astype(int)
    out.loc[out["cohort_n"] < MIN_GROUP_SIZE, "avg_raise_matched"] = None

    return pd.DataFrame({
        "employer_id": out["EmployerID"],
        "sector_id": out["SectorID"],
        "title_norm": out["Title_Norm"],
        "year": out["Year"].astype(int),
        "headcount": out["headcount"],
        "avg_salary": out["avg_salary"],
        "median_salary": out["median_salary"],
        "p90_salary": out["p90_salary"],
        "max_salary": out["max_salary"],
        "avg_total_comp": out["avg_total_comp"],
        "avg_raise_matched": out["avg_raise_matched"],
        "pct_female": out["pct_female"],
    }).sort_values(["employer_id", "sector_id", "title_norm", "year"]).reset_index(drop=True)


def build_combo_wide(combo_history: pd.DataFrame, employer_names: pd.Series, sector_name_map: dict) -> pd.DataFrame:
    key = ["employer_id", "sector_id", "title_norm"]
    span = combo_history.groupby(key)["year"].agg(first_year_present="min", last_year_present="max")
    years_present = combo_history.groupby(key)["year"].nunique().rename("years_present")
    cur = combo_history.sort_values("year").groupby(key).last()

    # Only combos big enough, right now, to say anything meaningful about.
    idx = cur[cur["headcount"] >= MIN_GROUP_SIZE].index

    out = pd.DataFrame({
        "employer_id": [i[0] for i in idx],
        "sector_id": [i[1] for i in idx],
        "title_norm": [i[2] for i in idx],
        "employer_name": [employer_names.get(i[0]) for i in idx],
        "sector_name": [sector_name_map.get(str(i[1])) for i in idx],
        "first_year_present": span.loc[idx, "first_year_present"].astype(int).values,
        "last_year_present": span.loc[idx, "last_year_present"].astype(int).values,
        "years_present": years_present.loc[idx].values,
        "current_year": cur.loc[idx, "year"].astype(int).values,
        "current_headcount": cur.loc[idx, "headcount"].values,
        "current_avg_salary": cur.loc[idx, "avg_salary"].values,
        "current_median_salary": cur.loc[idx, "median_salary"].values,
        "current_p90_salary": cur.loc[idx, "p90_salary"].values,
        "current_max_salary": cur.loc[idx, "max_salary"].values,
        "current_avg_total_comp": cur.loc[idx, "avg_total_comp"].values,
        "current_avg_raise_matched": cur.loc[idx, "avg_raise_matched"].values,
        "current_pct_female": cur.loc[idx, "pct_female"].values,
    })
    return out.reset_index(drop=True)


def build_combo_breakdown(history: pd.DataFrame, combo_wide: pd.DataFrame) -> pd.DataFrame:
    base = history[history["Title_Norm"].notna()].copy()
    lookup = combo_wide.rename(columns={
        "employer_id": "EmployerID", "sector_id": "SectorID", "title_norm": "Title_Norm", "current_year": "Year",
    })[["EmployerID", "SectorID", "Title_Norm", "Year"]]
    cur_rows = base.merge(lookup, on=["EmployerID", "SectorID", "Title_Norm", "Year"], how="inner")

    breakdown = compute_title_breakdown(cur_rows, ["EmployerID", "SectorID", "Title_Norm"])
    return breakdown.rename(columns={"EmployerID": "employer_id", "SectorID": "sector_id", "Title_Norm": "title_norm"})


def build_employer_position_profile_cube() -> dict:
    history, employees, sectors = load_source()
    sector_name_map = dict(zip(sectors["sector_id"].astype(str), sectors["canonical"]))
    idx = history.groupby("EmployerID")["Year"].idxmax()
    employer_names = history.loc[idx, ["EmployerID", "EmployerName"]].set_index("EmployerID")["EmployerName"]

    combo_history = build_combo_history(history, employees)
    combo_wide = build_combo_wide(combo_history, employer_names, sector_name_map)
    combo_breakdown = build_combo_breakdown(history, combo_wide)

    # Trim history to qualifying combos only — no point keeping trend rows for
    # combos that never got big enough to have a page.
    qualifying = combo_wide[["employer_id", "sector_id", "title_norm"]]
    combo_history = combo_history.merge(qualifying, on=["employer_id", "sector_id", "title_norm"], how="inner")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    combo_wide.to_parquet(os.path.join(OUTPUT_DIR, "employer_position_wide.parquet"), index=False)
    combo_history.to_parquet(os.path.join(OUTPUT_DIR, "employer_position_history.parquet"), index=False)
    combo_breakdown.to_parquet(os.path.join(OUTPUT_DIR, "employer_position_breakdown.parquet"), index=False)

    return update_manifest("employer_position_profile", {
        "employer_position_wide.parquet": len(combo_wide),
        "employer_position_history.parquet": len(combo_history),
        "employer_position_breakdown.parquet": len(combo_breakdown),
    })


if __name__ == "__main__":
    print(json.dumps(build_employer_position_profile_cube(), indent=2))
