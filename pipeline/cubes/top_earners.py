"""Builds the top_earners cube: one flat parquet table, one row per employee
disclosed in the dataset's latest year, with province/sector/employer/position
rank columns already computed — the Top Earners page filters and sorts this
table, it never re-derives a rank.

Dev-time script: `python -m pipeline.cubes.top_earners`.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from pipeline.manifest import update_manifest
from pipeline.rankings import compute_current_year_rankings

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

    cur = compute_current_year_rankings(history)
    cur = cur.merge(employees[["EmployeeID", "FirstName", "LastName"]], on="EmployeeID", how="left")
    cur["SectorName"] = cur["SectorID"].astype(str).map(sector_name_map)

    return pd.DataFrame({
        "employee_id": cur["EmployeeID"],
        "first_name": cur["FirstName"],
        "last_name": cur["LastName"],
        "year": cur["Year"].astype(int),
        "employer_id": cur["EmployerID"],
        "employer_name": cur["EmployerName"],
        "sector_id": cur["SectorID"],
        "sector_name": cur["SectorName"],
        "title_norm": cur["Title_Norm"],
        "job_title": cur["JobTitleNorm"],
        "salary_paid": cur["SalaryPaid"],
        "taxable_benefits": cur["TaxableBenefits"],
        "total_comp": cur["TotalComp"],
        "yoy_salary_increase": cur["YoYSalaryIncreaseClean"],
        "comparable_to_prior_year": cur["YoYComparable"],
        "rank_province": cur["RankProvince"],
        "province_pool": cur["ProvincePool"],
        "rank_sector": cur["RankSector"],
        "sector_pool": cur["SectorPool"],
        "rank_employer": cur["RankEmployer"],
        "employer_pool": cur["EmployerPool"],
        "rank_position": cur["RankPosition"],
        "position_pool": cur["PositionPool"],
    }).sort_values("total_comp", ascending=False).reset_index(drop=True)


def build_top_earners_cube() -> dict:
    table = build_top_earners_table()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    table.to_parquet(os.path.join(OUTPUT_DIR, "top_earners_current.parquet"), index=False)
    return update_manifest("top_earners", {"top_earners_current.parquet": len(table)})


if __name__ == "__main__":
    print(json.dumps(build_top_earners_cube(), indent=2))
