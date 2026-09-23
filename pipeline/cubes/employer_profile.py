"""Builds the employer_profile cube: three flat parquet tables in data/profiles/,
keyed by employer_id (and year, for employer_history). Always a full build — there
are only ~3,500 employers, no need for the employee cube's test/full split.

Dev-time script: `python -m pipeline.cubes.employer_profile`.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from pipeline.manifest import update_manifest

SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles"))

TOP_EARNERS_N = 10


def load_source() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    history = pd.read_parquet(os.path.join(SOURCE_DIR, "employment_history_enriched.parquet"))
    employees = pd.read_parquet(os.path.join(SOURCE_DIR, "employees_enriched.parquet"))
    employers = pd.read_parquet(os.path.join(SOURCE_DIR, "employer", "employers_canonical.parquet"))
    sectors = pd.read_parquet(os.path.join(SOURCE_DIR, "sectors_canonical.parquet"))
    return history, employees, employers, sectors


def build_employer_history(history: pd.DataFrame) -> pd.DataFrame:
    g = history.groupby(["EmployerID", "Year"])
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

    return pd.DataFrame({
        "employer_id": out["EmployerID"],
        "year": out["Year"].astype(int),
        "headcount": out["headcount"],
        "avg_salary": out["avg_salary"],
        "avg_total_comp": out["avg_total_comp"],
        "total_payroll": out["total_payroll"],
        "pct_newly_disclosed": out["pct_newly_disclosed"],
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
    })
    return out.reset_index(drop=True)


def build_top_earners(history: pd.DataFrame, employees: pd.DataFrame) -> pd.DataFrame:
    idx = history.groupby("EmployerID")["Year"].idxmax()
    current_year_by_employer = history.loc[idx, ["EmployerID", "Year"]].set_index("EmployerID")["Year"]

    cur_rows = history[history["Year"] == history["EmployerID"].map(current_year_by_employer)].copy()
    cur_rows = cur_rows.merge(employees[["EmployeeID", "FirstName", "LastName"]], on="EmployeeID", how="left")
    cur_rows["rank"] = cur_rows.groupby("EmployerID")["TotalComp"].rank(method="first", ascending=False).astype(int)
    top = cur_rows[cur_rows["rank"] <= TOP_EARNERS_N].sort_values(["EmployerID", "rank"])

    return pd.DataFrame({
        "employer_id": top["EmployerID"],
        "year": top["Year"].astype(int),
        "rank": top["rank"],
        "employee_id": top["EmployeeID"],
        "first_name": top["FirstName"],
        "last_name": top["LastName"],
        "job_title": top["JobTitleNorm"],
        "total_comp": top["TotalComp"],
    }).reset_index(drop=True)


def build_employer_profile_cube() -> dict:
    history, employees, employers, sectors = load_source()
    sector_name_map = dict(zip(sectors["sector_id"].astype(str), sectors["canonical"]))

    employer_history = build_employer_history(history)
    employer_wide = build_employer_wide(history, employer_history, employers, sector_name_map)
    top_earners = build_top_earners(history, employees)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    employer_wide.to_parquet(os.path.join(OUTPUT_DIR, "employer_wide.parquet"), index=False)
    employer_history.to_parquet(os.path.join(OUTPUT_DIR, "employer_history.parquet"), index=False)
    top_earners.to_parquet(os.path.join(OUTPUT_DIR, "employer_top_earners.parquet"), index=False)

    return update_manifest("employer_profile", {
        "employer_wide.parquet": len(employer_wide),
        "employer_history.parquet": len(employer_history),
        "employer_top_earners.parquet": len(top_earners),
    })


if __name__ == "__main__":
    print(json.dumps(build_employer_profile_cube(), indent=2))
