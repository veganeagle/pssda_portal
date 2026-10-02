"""Builds the notable_roles cube: the single highest-paid current-year
incumbent for a short curated list of recognizable civic/institutional
leadership titles (Mayor, Police Chief, ...). These are legitimately
one-or-few-per-employer roles, so the usual MIN_GROUP_SIZE=3 suppression used
everywhere else (position_profile, employer_position_profile) would hide
every one of them — this cube exists specifically to carve out that
exception for a small, hand-picked list, not to relax the rule generally.

Matches on JobTitleNorm text directly rather than Title_Norm: several of
these roles used to collapse into a shared, ambiguous Title_Norm bucket
upstream (Police Chief and Fire Chief both normalized to the generic
"CHIEF" until that was split) — matching on raw text here is what originally
surfaced that bug, and is kept even now that the dictionary is fixed, since
it's still the more precise way to pick one specific role out by name.

Dev-time script: `python -m pipeline.cubes.notable_roles`.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from pipeline.manifest import update_manifest
from pipeline.rankings import compute_current_year_rankings

SOURCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles"))

# (display label, filter function over the current-year history frame)
ROLES: list[tuple[str, callable]] = [
    ("Mayor", lambda df: df["Title_Norm"] == "MAYOR"),
    ("Police Chief", lambda df: (
        df["JobTitleNorm"].str.contains("POLICE CHIEF", na=False)
        | df["JobTitleNorm"].str.contains("CHIEF OF POLICE", na=False)
    ) & ~df["JobTitleNorm"].str.contains("DEPUTY", na=False)),
    ("Hospital CEO", lambda df: (df["SectorID"].astype(str) == "6") & (df["Title_Norm"] == "CEO")),
    ("Director of Education", lambda df: df["JobTitleNorm"].str.contains("DIRECTOR OF EDUCATION", na=False)),
    ("Chief Administrative Officer", lambda df: df["Title_Norm"] == "CAO"),
    ("College/University President", lambda df: (
        df["JobTitleNorm"].str.contains("PRESIDENT", na=False)
        & df["SectorID"].astype(str).isin(["1", "11"])
        & ~df["JobTitleNorm"].str.contains("VICE|ASSOCIATE|ASSISTANT", na=False, regex=True)
    )),
]


def load_source() -> pd.DataFrame:
    return pd.read_parquet(os.path.join(SOURCE_DIR, "employment_history_enriched.parquet"))


def build_notable_roles_table() -> pd.DataFrame:
    history = load_source()
    cur = compute_current_year_rankings(history)
    current_year = int(cur["Year"].max())

    rows = []
    for label, filt in ROLES:
        pool = cur[filt(cur)]
        if pool.empty:
            continue
        top = pool.loc[pool["SalaryPaid"].idxmax()]
        yoy = top["YoYSalaryIncreaseClean"]
        rows.append({
            "role_label": label,
            "year": current_year,
            "employee_id": top["EmployeeID"],
            "employer_id": top["EmployerID"],
            "employer_name": top["EmployerName"],
            "sector_name": top.get("SectorID"),
            "job_title_raw": top["JobTitleRaw"],
            "salary_paid": float(top["SalaryPaid"]),
            "pool_size": int(len(pool)),
            "yoy_salary_increase": float(yoy) if pd.notna(yoy) else None,
            "comparable_to_prior_year": bool(top["YoYComparable"]),
        })

    table = pd.DataFrame(rows)
    sectors = pd.read_parquet(os.path.join(SOURCE_DIR, "sectors_canonical.parquet"))
    sector_name_map = dict(zip(sectors["sector_id"].astype(str), sectors["canonical"]))
    table["sector_name"] = table["sector_name"].astype(str).map(sector_name_map)

    employees = pd.read_parquet(os.path.join(SOURCE_DIR, "employees_enriched.parquet"))
    table = table.merge(employees[["EmployeeID", "FirstName", "LastName"]],
                         left_on="employee_id", right_on="EmployeeID", how="left")
    table = table.rename(columns={"FirstName": "first_name", "LastName": "last_name"}).drop(columns=["EmployeeID"])
    return table.sort_values("salary_paid", ascending=False).reset_index(drop=True)


def build_notable_roles_cube() -> dict:
    table = build_notable_roles_table()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    table.to_parquet(os.path.join(OUTPUT_DIR, "notable_roles_current.parquet"), index=False)
    return update_manifest("notable_roles", {"notable_roles_current.parquet": len(table)})


if __name__ == "__main__":
    print(json.dumps(build_notable_roles_cube(), indent=2))
