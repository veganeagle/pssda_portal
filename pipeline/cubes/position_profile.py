"""Builds the position_profile cube: three flat parquet tables in data/profiles/,
keyed by (sector_id, title_norm) — the safe comparable unit (raw Title_Norm alone
spans unrelated domains, e.g. "Inspector" at a police service vs. a health unit).

Implements the matched-cohort raise metric from SUNSHINE.md #2: a same-incumbent
average, not a same-role year-over-year average of two different populations.

Dev-time script: `python -m pipeline.cubes.position_profile`.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from pipeline.gender import compute_pct_female
from pipeline.manifest import update_manifest
from pipeline.matched_cohort import matched_cohort_flag

SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles"))

MIN_EMPLOYER_GROUP_SIZE = 3  # same rationale as the payband cube — suppress tiny, noisy cells


def load_source() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    history = pd.read_parquet(os.path.join(SOURCE_DIR, "employment_history_enriched.parquet"))
    employees = pd.read_parquet(os.path.join(SOURCE_DIR, "employees_enriched.parquet"))
    sectors = pd.read_parquet(os.path.join(SOURCE_DIR, "sectors_canonical.parquet"))
    return history, employees, sectors


def build_position_history(history: pd.DataFrame, employees: pd.DataFrame) -> pd.DataFrame:
    base = history[history["Title_Norm"].notna()].copy()
    base["MatchedCohort"] = matched_cohort_flag(base, ["SectorID", "Title_Norm"])
    base = base.merge(employees[["EmployeeID", "Prob_Female"]], on="EmployeeID", how="left")

    key = ["SectorID", "Title_Norm", "Year"]
    headcount = base.groupby(key)["EmployeeID"].size().rename("headcount")
    avg_salary = base.groupby(key)["SalaryPaid"].mean().round(0).rename("avg_salary")
    avg_total_comp = base.groupby(key)["TotalComp"].mean().round(0).rename("avg_total_comp")
    promotions = base.groupby(key)["PromotionFlag"].sum().astype(int).rename("promotions")

    matched = base[base["MatchedCohort"]]
    avg_raise_matched = matched.groupby(key)["YoYSalaryIncrease"].mean().round(4).rename("avg_raise_matched")
    cohort_size_matched = matched.groupby(key)["EmployeeID"].size().rename("cohort_size_matched")

    gender = compute_pct_female(base, key).set_index(key)["pct_female"].rename("pct_female")

    out = pd.concat(
        [headcount, avg_salary, avg_total_comp, promotions, avg_raise_matched, cohort_size_matched, gender], axis=1
    ).reset_index()
    out["cohort_size_matched"] = out["cohort_size_matched"].fillna(0).astype(int)

    return pd.DataFrame({
        "sector_id": out["SectorID"],
        "title_norm": out["Title_Norm"],
        "year": out["Year"].astype(int),
        "headcount": out["headcount"],
        "avg_salary": out["avg_salary"],
        "avg_total_comp": out["avg_total_comp"],
        "promotions": out["promotions"],
        "avg_raise_matched": out["avg_raise_matched"],
        "cohort_size_matched": out["cohort_size_matched"],
        "pct_female": out["pct_female"],
    }).sort_values(["sector_id", "title_norm", "year"]).reset_index(drop=True)


def build_position_wide(position_history: pd.DataFrame, sector_name_map: dict) -> pd.DataFrame:
    span = position_history.groupby(["sector_id", "title_norm"])["year"].agg(
        first_year_present="min", last_year_present="max"
    )
    years_present = position_history.groupby(["sector_id", "title_norm"])["year"].nunique()
    cur = position_history.sort_values("year").groupby(["sector_id", "title_norm"]).last()

    idx = span.index
    out = pd.DataFrame({
        "sector_id": [i[0] for i in idx],
        "title_norm": [i[1] for i in idx],
        "sector_name": [sector_name_map.get(str(i[0])) for i in idx],
        "first_year_present": span["first_year_present"].astype(int).values,
        "last_year_present": span["last_year_present"].astype(int).values,
        "years_present": years_present.values,
        "current_year": cur["year"].astype(int).values,
        "current_headcount": cur["headcount"].values,
        "current_avg_salary": cur["avg_salary"].values,
        "current_avg_total_comp": cur["avg_total_comp"].values,
        "current_promotions": cur["promotions"].values,
        "current_avg_raise_matched": cur["avg_raise_matched"].values,
        "current_cohort_size_matched": cur["cohort_size_matched"].values,
        "current_pct_female": cur["pct_female"].values,
    })
    return out.reset_index(drop=True)


def build_position_by_employer(history: pd.DataFrame) -> pd.DataFrame:
    """Current-year-per-position breakdown by employer — the cross-municipality
    leaderboard (e.g. every municipality's Police Constable, ranked)."""
    base = history[history["Title_Norm"].notna()].copy()
    current_year_by_position = base.groupby(["SectorID", "Title_Norm"])["Year"].transform("max")
    cur = base[base["Year"] == current_year_by_position].copy()
    cur["MatchedCohort"] = matched_cohort_flag(base, ["SectorID", "Title_Norm", "EmployerID"])[
        base["Year"].eq(current_year_by_position).values
    ]

    key = ["SectorID", "Title_Norm", "EmployerID"]
    g = cur.groupby(key).agg(
        employer_name=("EmployerName", "first"),
        year=("Year", "first"),
        headcount=("EmployeeID", "size"),
        avg_total_comp=("TotalComp", "mean"),
        max_salary=("SalaryPaid", "max"),
        new_entrants=("TenureOnList", lambda s: int((s == 1).sum())),
    ).reset_index()
    g = g[g["headcount"] >= MIN_EMPLOYER_GROUP_SIZE].copy()
    g["avg_total_comp"] = g["avg_total_comp"].round(0)
    g["max_salary"] = g["max_salary"].round(0)
    g["rank"] = g.groupby(["SectorID", "Title_Norm"])["headcount"].rank(method="dense", ascending=False).astype(int)

    matched = cur[cur["MatchedCohort"]]
    avg_raise = matched.groupby(key)["YoYSalaryIncrease"].mean().round(4).rename("avg_raise_matched")
    cohort_n = matched.groupby(key)["EmployeeID"].size().rename("cohort_n")
    g = g.merge(pd.concat([avg_raise, cohort_n], axis=1).reset_index(), on=key, how="left")
    g["cohort_n"] = g["cohort_n"].fillna(0).astype(int)
    g.loc[g["cohort_n"] < MIN_EMPLOYER_GROUP_SIZE, "avg_raise_matched"] = None

    return pd.DataFrame({
        "sector_id": g["SectorID"],
        "title_norm": g["Title_Norm"],
        "employer_id": g["EmployerID"],
        "employer_name": g["employer_name"],
        "year": g["year"].astype(int),
        "headcount": g["headcount"],
        "avg_total_comp": g["avg_total_comp"],
        "max_salary": g["max_salary"],
        "new_entrants": g["new_entrants"],
        "avg_raise_matched": g["avg_raise_matched"],
        "rank": g["rank"],
    }).sort_values(["sector_id", "title_norm", "rank"]).reset_index(drop=True)


def build_position_profile_cube() -> dict:
    history, employees, sectors = load_source()
    sector_name_map = dict(zip(sectors["sector_id"].astype(str), sectors["canonical"]))

    position_history = build_position_history(history, employees)
    position_wide = build_position_wide(position_history, sector_name_map)
    by_employer = build_position_by_employer(history)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    position_wide.to_parquet(os.path.join(OUTPUT_DIR, "position_wide.parquet"), index=False)
    position_history.to_parquet(os.path.join(OUTPUT_DIR, "position_history.parquet"), index=False)
    by_employer.to_parquet(os.path.join(OUTPUT_DIR, "position_by_employer.parquet"), index=False)

    return update_manifest("position_profile", {
        "position_wide.parquet": len(position_wide),
        "position_history.parquet": len(position_history),
        "position_by_employer.parquet": len(by_employer),
    })


if __name__ == "__main__":
    print(json.dumps(build_position_profile_cube(), indent=2))
