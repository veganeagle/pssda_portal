"""Single-employee lookup: EmployeeID -> EmployeeProfile. Assumes the caller has
already resolved a search down to one EmployeeID.
"""
from __future__ import annotations

from typing import Optional

from access._rows import records as _records
from access.db import query
from models.employee_profile import CurrentRole, EmployeeProfile, PaybandStanding, YearRecord


def get_employee_profile(employee_id: str) -> Optional[EmployeeProfile]:
    wide = query("SELECT * FROM employee_wide WHERE employee_id = ?", [employee_id])
    if wide.empty:
        return None
    w = _records(wide)[0]

    history_df = query("SELECT * FROM employee_history WHERE employee_id = ? ORDER BY year DESC", [employee_id])
    payband_df = query(
        "SELECT * FROM employee_payband_standing WHERE employee_id = ? ORDER BY year, peer_group", [employee_id]
    )

    current = CurrentRole(
        year=w["current_year"], employer_id=w["current_employer_id"], employer_name=w["current_employer_name"],
        sector_id=w["current_sector_id"], sector_name=w["current_sector_name"],
        subsector=w["current_subsector"], job_title=w["current_job_title"],
        title_norm=w["current_title_norm"], region=w["current_region"], municipality=w["current_municipality"],
        salary_paid=w["current_salary_paid"], taxable_benefits=w["current_taxable_benefits"],
        total_comp=w["current_total_comp"],
    )
    history = [YearRecord(**row) for row in _records(history_df, exclude=("employee_id",))]
    paybands = [PaybandStanding(**row) for row in _records(payband_df, exclude=("employee_id",))]

    return EmployeeProfile(
        employee_id=w["employee_id"], first_name=w["first_name"], last_name=w["last_name"], middle=w["middle"],
        first_initial=w["first_initial"], first_seen_year=w["first_seen_year"],
        first_seen_year_left_censored=w["first_seen_year_left_censored"], last_seen_year=w["last_seen_year"],
        years_disclosed=w["years_disclosed"], prob_female=w["prob_female"],
        current=current, history=history, paybands=paybands,
    )


if __name__ == "__main__":
    import json

    total = query("SELECT COUNT(*) AS n FROM employee_wide")["n"].iloc[0]
    ids = query("SELECT employee_id FROM employee_wide LIMIT 5")["employee_id"].tolist()
    print(f"employee_wide has {total} employee(s); sampling {len(ids)}: {ids}")
    for eid in ids:
        profile = get_employee_profile(eid)
        assert profile is not None
        payload = profile.model_dump_json()
        json.loads(payload)  # fails loudly on non-standard JSON (e.g. NaN)
        print(f"  {eid}: {profile.first_name} {profile.last_name} — {len(profile.history)} history rows, "
              f"{len(profile.paybands)} payband rows, {len(payload)} bytes, round-trip OK")

    print(f"unknown id -> {get_employee_profile('not-a-real-id')!r}")
