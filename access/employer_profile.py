"""Single-employer lookup: EmployerID -> EmployerProfile."""
from __future__ import annotations

from typing import Optional

from access._rows import records
from access.db import query
from models.employer_profile import EmployerProfile, EmployerYearRecord, TopEarner


def get_employer_profile(employer_id: str) -> Optional[EmployerProfile]:
    wide = query("SELECT * FROM employer_wide WHERE employer_id = ?", [employer_id])
    if wide.empty:
        return None
    w = records(wide)[0]

    history_df = query("SELECT * FROM employer_history WHERE employer_id = ? ORDER BY year", [employer_id])
    history = [EmployerYearRecord(**row) for row in records(history_df, exclude=("employer_id",))]
    current = next((h for h in history if h.year == w["current_year"]), history[-1])

    top_df = query(
        "SELECT * FROM employer_top_earners WHERE employer_id = ? ORDER BY rank", [employer_id]
    )
    top_earners = [TopEarner(**row) for row in records(top_df, exclude=("employer_id", "year"))]

    return EmployerProfile(
        employer_id=w["employer_id"], employer_name=w["employer_name"], sector_id=w["sector_id"],
        sector_name=w["sector_name"], subsector=w["subsector"], region=w["region"],
        municipality=w["municipality"], population=w["population"],
        first_year_present=w["first_year_present"], last_year_present=w["last_year_present"],
        years_present=w["years_present"], current=current, history=history, top_earners=top_earners,
    )


if __name__ == "__main__":
    import json

    ids = query("SELECT employer_id FROM employer_wide ORDER BY current_headcount DESC LIMIT 5")["employer_id"].tolist()
    for eid in ids:
        p = get_employer_profile(eid)
        assert p is not None
        payload = p.model_dump_json()
        json.loads(payload)
        print(f"  {eid}: {p.employer_name} — {len(p.history)} yrs, {len(p.top_earners)} top earners, {len(payload)} bytes, OK")

    print(f"unknown id -> {get_employer_profile('not-a-real-id')!r}")
