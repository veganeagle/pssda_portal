"""Builds the employer_profile cube: four flat parquet tables in data/profiles/,
keyed by employer_id (and year, for employer_history). Always a full build — there
are only ~3,500 employers, no need for the employee cube's test/full split.

Dev-time script: `python -m pipeline.cubes.employer_profile`.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from pipeline.gender import compute_pct_female
from pipeline.manifest import update_manifest
from pipeline.matched_cohort import matched_cohort_flag
from pipeline.rankings import compute_current_year_rankings
from pipeline.title_breakdown import compute_title_breakdown

SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles"))

TOP_EARNERS_N = 10
TOP_POSITIONS_N = 10
MIN_MATCHED_COHORT = 3  # same rationale as the payband cube — suppress tiny, noisy cells


def load_source() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    history = pd.read_parquet(os.path.join(SOURCE_DIR, "employment_history_enriched.parquet"))
    employees = pd.read_parquet(os.path.join(SOURCE_DIR, "employees_enriched.parquet"))
    employers = pd.read_parquet(os.path.join(SOURCE_DIR, "employer", "employers_canonical.parquet"))
    sectors = pd.read_parquet(os.path.join(SOURCE_DIR, "sectors_canonical.parquet"))
    return history, employees, employers, sectors


def build_employer_history(history: pd.DataFrame, employees: pd.DataFrame) -> pd.DataFrame:
    base = history.merge(employees[["EmployeeID", "Prob_Female"]], on="EmployeeID", how="left")

    key = ["EmployerID", "Year"]
    g = base.groupby(key)
    out = g.agg(
        headcount=("EmployeeID", "size"),
        avg_salary=("SalaryPaid", "mean"),
        avg_total_comp=("TotalComp", "mean"),
        total_payroll=("SalaryPaid", "sum"),
        newly_disclosed=("TenureOnList", lambda s: (s == 1).sum()),
    ).reset_index()
    out["pct_newly_disclosed"] = (out["newly_disclosed"] / out["headcount"] * 100).round(1)
    out = out.drop(columns="newly_disclosed")
    out[["avg_salary", "avg_total_comp", "total_payroll"]] = out[["avg_salary", "avg_total_comp", "total_payroll"]].round(0)

    gender = compute_pct_female(base, key).set_index(key)["pct_female"].rename("pct_female")
    out = out.merge(gender.reset_index(), on=key, how="left")

    return pd.DataFrame({
        "employer_id": out["EmployerID"],
        "year": out["Year"].astype(int),
        "headcount": out["headcount"],
        "avg_salary": out["avg_salary"],
        "avg_total_comp": out["avg_total_comp"],
        "total_payroll": out["total_payroll"],
        "pct_newly_disclosed": out["pct_newly_disclosed"],
        "pct_female": out["pct_female"],
    }).sort_values(["employer_id", "year"]).reset_index(drop=True)


def build_employer_wide(
    history: pd.DataFrame, employer_history: pd.DataFrame, employers: pd.DataFrame, sector_name_map: dict
) -> pd.DataFrame:
    idx = history.groupby("EmployerID")["Year"].idxmax()
    current_names = history.loc[idx, ["EmployerID", "EmployerName", "SectorID"]].set_index("EmployerID")

    span = history.groupby("EmployerID")["Year"].agg(first_year_present="min", last_year_present="max")
    years_present = history.groupby("EmployerID")["Year"].nunique().rename("years_present")

    cur = employer_history.sort_values("year").groupby("employer_id").last()

    ref = employers.set_index("CanonicalEmployerID")
    population = pd.to_numeric(ref["Population"], errors="coerce")
    population = population.where(population > 0)  # 0 means "not municipal", not "population zero"

    employer_ids = current_names.index
    out = pd.DataFrame({
        "employer_id": employer_ids,
        "employer_name": current_names["EmployerName"],
        "sector_id": current_names["SectorID"],
        "sector_name": current_names["SectorID"].astype(str).map(sector_name_map),
        "subsector": ref["CanonicalSubSector"].reindex(employer_ids).values,
        "region": ref["Region"].reindex(employer_ids).values,
        "municipality": ref["Municipality"].reindex(employer_ids).values,
        "population": population.reindex(employer_ids).values,
        "first_year_present": span.loc[employer_ids, "first_year_present"].astype(int).values,
        "last_year_present": span.loc[employer_ids, "last_year_present"].astype(int).values,
        "years_present": years_present.loc[employer_ids].values,
        "current_year": cur.loc[employer_ids, "year"].astype(int).values,
        "current_headcount": cur.loc[employer_ids, "headcount"].values,
        "current_avg_salary": cur.loc[employer_ids, "avg_salary"].values,
        "current_avg_total_comp": cur.loc[employer_ids, "avg_total_comp"].values,
        "current_total_payroll": cur.loc[employer_ids, "total_payroll"].values,
        "current_pct_newly_disclosed": cur.loc[employer_ids, "pct_newly_disclosed"].values,
        "current_pct_female": cur.loc[employer_ids, "pct_female"].values,
    })
    return out.reset_index(drop=True)


def build_top_earners(history: pd.DataFrame, employees: pd.DataFrame, rankings: pd.DataFrame) -> pd.DataFrame:
    idx = history.groupby("EmployerID")["Year"].idxmax()
    current_year_by_employer = history.loc[idx, ["EmployerID", "Year"]].set_index("EmployerID")["Year"]

    cur_rows = history[history["Year"] == history["EmployerID"].map(current_year_by_employer)].copy()
    cur_rows = cur_rows.merge(employees[["EmployeeID", "FirstName", "LastName"]], on="EmployeeID", how="left")
    cur_rows["rank"] = cur_rows.groupby("EmployerID")["TotalComp"].rank(method="first", ascending=False).astype(int)
    top = cur_rows[cur_rows["rank"] <= TOP_EARNERS_N].sort_values(["EmployerID", "rank"]).copy()

    # Same-employee YoY, independent of dataset-wide current year — works even for
    # an employer whose own last disclosed year isn't the dataset's latest.
    comparable = (top["GapFlag"] == 0) & (top["TenureOnList"] > 1)
    top["yoy_salary_increase"] = top["YoYSalaryIncrease"].where(comparable)
    top["comparable_to_prior_year"] = comparable

    # Sector/position rank only exists for the dataset's actual latest year — an
    # employer whose "current" is an earlier year (e.g. dissolved/merged) won't
    # have a match here, and that's correct: can't fairly rank a 2020 salary
    # against 2025's population.
    top = top.merge(
        rankings[["EmployeeID", "RankSector", "SectorPool", "RankPosition", "PositionPool"]],
        on="EmployeeID", how="left",
    )

    return pd.DataFrame({
        "employer_id": top["EmployerID"],
        "year": top["Year"].astype(int),
        "rank": top["rank"],
        "employee_id": top["EmployeeID"],
        "first_name": top["FirstName"],
        "last_name": top["LastName"],
        "job_title": top["JobTitleNorm"],
        "total_comp": top["TotalComp"],
        "yoy_salary_increase": top["yoy_salary_increase"],
        "comparable_to_prior_year": top["comparable_to_prior_year"],
        "rank_sector": top["RankSector"],
        "sector_pool": top["SectorPool"],
        "rank_position": top["RankPosition"],
        "position_pool": top["PositionPool"],
    }).reset_index(drop=True)


def build_top_positions(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Current-year-per-employer breakdown by position, ranked by headcount —
    "what roles does this employer have the most of," with each role's own
    salary band and matched-cohort raise. Returns (top_positions, breakdown) —
    the label is the generic Title_Norm (e.g. "Teacher"), never one arbitrarily
    picked raw variant (that previously mislabeled a merged Elementary+Secondary
    group as if it were Elementary-only); breakdown carries the real composition.
    """
    idx = history.groupby("EmployerID")["Year"].idxmax()
    current_year_by_employer = history.loc[idx, ["EmployerID", "Year"]].set_index("EmployerID")["Year"]

    base = history[history["Title_Norm"].notna()].copy()
    is_current = base["Year"] == base["EmployerID"].map(current_year_by_employer)
    base["MatchedCohort"] = matched_cohort_flag(base, ["SectorID", "Title_Norm", "EmployerID"])
    cur = base[is_current].copy()

    key = ["EmployerID", "Title_Norm"]
    g = cur.groupby(key).agg(
        sector_id=("SectorID", "first"),
        year=("Year", "first"),
        headcount=("EmployeeID", "size"),
        avg_salary=("SalaryPaid", "mean"),
        median_salary=("SalaryPaid", "median"),
        p90_salary=("SalaryPaid", lambda s: s.quantile(0.9)),
        avg_total_comp=("TotalComp", "mean"),
    ).reset_index()
    money_cols = ["avg_salary", "median_salary", "p90_salary", "avg_total_comp"]
    g[money_cols] = g[money_cols].round(0)

    matched = cur[cur["MatchedCohort"]]
    avg_raise = matched.groupby(key)["YoYSalaryIncrease"].mean().round(4).rename("avg_raise_matched")
    cohort_n = matched.groupby(key)["EmployeeID"].size().rename("cohort_n")
    g = g.merge(pd.concat([avg_raise, cohort_n], axis=1).reset_index(), on=key, how="left")
    g["cohort_n"] = g["cohort_n"].fillna(0).astype(int)
    g.loc[g["cohort_n"] < MIN_MATCHED_COHORT, "avg_raise_matched"] = None

    g["rank"] = g.groupby("EmployerID")["headcount"].rank(method="first", ascending=False).astype(int)
    top = g[g["rank"] <= TOP_POSITIONS_N].sort_values(["EmployerID", "rank"])

    top_positions = pd.DataFrame({
        "employer_id": top["EmployerID"],
        "sector_id": top["sector_id"],
        "title_norm": top["Title_Norm"],
        "year": top["year"].astype(int),
        "rank": top["rank"],
        "headcount": top["headcount"],
        "avg_salary": top["avg_salary"],
        "median_salary": top["median_salary"],
        "p90_salary": top["p90_salary"],
        "avg_total_comp": top["avg_total_comp"],
        "avg_raise_matched": top["avg_raise_matched"],
    }).reset_index(drop=True)

    # Breakdown only for the (employer, title) pairs that actually made top 10 —
    # no need to compute it for the long tail that's never displayed.
    top_pairs = cur.merge(top[["EmployerID", "Title_Norm"]], on=["EmployerID", "Title_Norm"], how="inner")
    breakdown = compute_title_breakdown(top_pairs, ["EmployerID", "Title_Norm"])
    breakdown = breakdown.rename(columns={"EmployerID": "employer_id", "Title_Norm": "title_norm"})

    return top_positions, breakdown


def build_employer_profile_cube() -> dict:
    history, employees, employers, sectors = load_source()
    sector_name_map = dict(zip(sectors["sector_id"].astype(str), sectors["canonical"]))
    rankings = compute_current_year_rankings(history)

    employer_history = build_employer_history(history, employees)
    employer_wide = build_employer_wide(history, employer_history, employers, sector_name_map)
    top_earners = build_top_earners(history, employees, rankings)
    top_positions, top_position_breakdown = build_top_positions(history)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    employer_wide.to_parquet(os.path.join(OUTPUT_DIR, "employer_wide.parquet"), index=False)
    employer_history.to_parquet(os.path.join(OUTPUT_DIR, "employer_history.parquet"), index=False)
    top_earners.to_parquet(os.path.join(OUTPUT_DIR, "employer_top_earners.parquet"), index=False)
    top_positions.to_parquet(os.path.join(OUTPUT_DIR, "employer_top_positions.parquet"), index=False)
    top_position_breakdown.to_parquet(os.path.join(OUTPUT_DIR, "employer_top_position_breakdown.parquet"), index=False)

    return update_manifest("employer_profile", {
        "employer_wide.parquet": len(employer_wide),
        "employer_history.parquet": len(employer_history),
        "employer_top_earners.parquet": len(top_earners),
        "employer_top_positions.parquet": len(top_positions),
        "employer_top_position_breakdown.parquet": len(top_position_breakdown),
    })


if __name__ == "__main__":
    print(json.dumps(build_employer_profile_cube(), indent=2))
