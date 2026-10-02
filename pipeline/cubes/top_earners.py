"""Builds the top_earners cube: one flat parquet table, one row per employee
per disclosed year, with that year's own province/sector/employer/position
rank columns already computed (ranked within that year's population, not
mixed across years) — the Top Earners page filters, sorts, and steps between
years on this table, it never re-derives a rank.

Dev-time script: `python -m pipeline.cubes.top_earners`.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from pipeline.manifest import update_manifest
from pipeline.rankings import compute_rankings_for_year

SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles"))


def load_source() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    history = pd.read_parquet(os.path.join(SOURCE_DIR, "employment_history_enriched.parquet"))
    employees = pd.read_parquet(os.path.join(SOURCE_DIR, "employees_enriched.parquet"))
    sectors = pd.read_parquet(os.path.join(SOURCE_DIR, "sectors_canonical.parquet"))
    return history, employees, sectors


def build_top_earners_table() -> pd.DataFrame:
    history, employees, sectors = load_source()
    sector_name_map = dict(zip(sectors["sector_id"].astype(str), sectors["canonical"]))

    years = sorted(history["Year"].unique())
    ranked = pd.concat([compute_rankings_for_year(history, int(y)) for y in years], ignore_index=True)
    ranked = ranked.merge(employees[["EmployeeID", "FirstName", "LastName"]], on="EmployeeID", how="left")
    ranked["SectorName"] = ranked["SectorID"].astype(str).map(sector_name_map)

    return pd.DataFrame({
        "employee_id": ranked["EmployeeID"],
        "first_name": ranked["FirstName"],
        "last_name": ranked["LastName"],
        "year": ranked["Year"].astype(int),
        "employer_id": ranked["EmployerID"],
        "employer_name": ranked["EmployerName"],
        "sector_id": ranked["SectorID"],
        "sector_name": ranked["SectorName"],
        "title_norm": ranked["Title_Norm"],
        "job_title": ranked["JobTitleNorm"],
        "salary_paid": ranked["SalaryPaid"],
        "taxable_benefits": ranked["TaxableBenefits"],
        "total_comp": ranked["TotalComp"],
        "yoy_salary_increase": ranked["YoYSalaryIncreaseClean"],
        "comparable_to_prior_year": ranked["YoYComparable"],
        "rank_province": ranked["RankProvince"],
        "province_pool": ranked["ProvincePool"],
        "rank_sector": ranked["RankSector"],
        "sector_pool": ranked["SectorPool"],
        "rank_employer": ranked["RankEmployer"],
        "employer_pool": ranked["EmployerPool"],
        "rank_position": ranked["RankPosition"],
        "position_pool": ranked["PositionPool"],
    }).sort_values(["year", "total_comp"], ascending=[True, False]).reset_index(drop=True)


def build_top_earners_cube() -> dict:
    table = build_top_earners_table()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    table.to_parquet(os.path.join(OUTPUT_DIR, "top_earners_history.parquet"), index=False)
    return update_manifest("top_earners", {"top_earners_history.parquet": len(table)})


if __name__ == "__main__":
    print(json.dumps(build_top_earners_cube(), indent=2))
