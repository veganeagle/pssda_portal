"""Single employer+position ("combo") lookup: (employer_id, sector_id, title_norm)
-> EmployerPositionProfile. Only ever reached with a key already resolved from an
employer or position page — no search/browse for this one.
"""
from __future__ import annotations

from typing import Optional

from access._rows import records
from access.db import query
from models.employer_position_profile import ComboYearRecord, EmployerPositionProfile
from models.employer_profile import TitleVariant


def get_employer_position_profile(
    employer_id: str, sector_id: str, title_norm: str
) -> Optional[EmployerPositionProfile]:
    wide = query(
        "SELECT * FROM employer_position_wide WHERE employer_id = ? AND sector_id = ? AND title_norm = ?",
        [employer_id, sector_id, title_norm],
    )
    if wide.empty:
        return None
    w = records(wide)[0]

    history_df = query(
        "SELECT * FROM employer_position_history WHERE employer_id = ? AND sector_id = ? AND title_norm = ? "
        "ORDER BY year DESC",
        [employer_id, sector_id, title_norm],
    )
    history = [
        ComboYearRecord(**row) for row in records(history_df, exclude=("employer_id", "sector_id", "title_norm"))
    ]
    current = next((h for h in history if h.year == w["current_year"]), history[0])

    variants_df = query(
        "SELECT * FROM employer_position_breakdown WHERE employer_id = ? AND sector_id = ? AND title_norm = ?",
        [employer_id, sector_id, title_norm],
    )
    variants = [
        TitleVariant(**row) for row in records(variants_df, exclude=("employer_id", "sector_id", "title_norm"))
    ]

    return EmployerPositionProfile(
        employer_id=w["employer_id"], employer_name=w["employer_name"], sector_id=w["sector_id"],
        sector_name=w["sector_name"], title_norm=w["title_norm"],
        first_year_present=w["first_year_present"], last_year_present=w["last_year_present"],
        years_present=w["years_present"], current=current, history=history, variants=variants,
    )


if __name__ == "__main__":
    import json

    rows = query(
        "SELECT employer_id, sector_id, title_norm FROM employer_position_wide "
        "ORDER BY current_headcount DESC LIMIT 5"
    ).to_dict(orient="records")
    for r in rows:
        p = get_employer_position_profile(r["employer_id"], r["sector_id"], r["title_norm"])
        assert p is not None
        payload = p.model_dump_json()
        json.loads(payload)
        print(f"  {r['employer_id']}/{r['title_norm']}: {p.employer_name} — {len(p.history)} yrs, "
              f"{len(p.variants)} variants, {len(payload)} bytes, OK")

    print(f"unknown -> {get_employer_position_profile('nope', '99', 'NOPE')!r}")
