"""Single-employer lookup: EmployerID -> EmployerProfile."""
from __future__ import annotations

from typing import Optional

from access._rows import records
from access.db import query
from models.employer_profile import (
    EmployerProfile,
    EmployerSearchResult,
    EmployerYearRecord,
    TitleVariant,
    TopEarner,
    TopPosition,
)

SEARCH_LIMIT = 50


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_employers(
    name_contains: str | None = None, sector_id: str | None = None, limit: int | None = SEARCH_LIMIT
) -> list[EmployerSearchResult]:
    conditions = []
    params: list = []
    if name_contains:
        conditions.append("LOWER(employer_name) LIKE LOWER(?) ESCAPE '\\'")
        params.append(f"%{_escape_like(name_contains)}%")
    if sector_id:
        conditions.append("sector_id = ?")
        params.append(sector_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_clause = "LIMIT ?" if limit is not None else ""
    sql = f"""
        SELECT employer_id, employer_name, sector_id, sector_name, current_year,
               current_headcount, current_avg_total_comp
        FROM employer_wide
        {where_clause}
        ORDER BY current_headcount DESC
        {limit_clause}
    """
    if limit is not None:
        params.append(limit)
    df = query(sql, params)
    return [EmployerSearchResult(**row) for row in records(df)]


def sector_employer_counts() -> list[dict]:
    """Employer count per sector, province-wide — for the "employers by
    sector" overview bar list on the search page. Excludes the sentinel
    sectors (-1 unknown, 99 seconded) just like the sector picker does.
    """
    df = query("""
        SELECT sector_id, sector_name, COUNT(*) AS employer_count
        FROM employer_wide WHERE sector_id NOT IN ('-1', '99')
        GROUP BY sector_id, sector_name ORDER BY employer_count DESC
    """)
    return records(df)


def get_employer_profile(employer_id: str) -> Optional[EmployerProfile]:
    wide = query("SELECT * FROM employer_wide WHERE employer_id = ?", [employer_id])
    if wide.empty:
        return None
    w = records(wide)[0]

    history_df = query("SELECT * FROM employer_history WHERE employer_id = ? ORDER BY year DESC", [employer_id])
    history = [EmployerYearRecord(**row) for row in records(history_df, exclude=("employer_id",))]
    current = next((h for h in history if h.year == w["current_year"]), history[-1])

    top_df = query(
        "SELECT * FROM employer_top_earners WHERE employer_id = ? ORDER BY rank", [employer_id]
    )
    top_earners = [TopEarner(**row) for row in records(top_df, exclude=("employer_id", "year"))]

    positions_df = query(
        "SELECT * FROM employer_top_positions WHERE employer_id = ? ORDER BY rank", [employer_id]
    )
    variants_df = query(
        "SELECT * FROM employer_top_position_breakdown WHERE employer_id = ?", [employer_id]
    )
    variants_by_title: dict[str, list[TitleVariant]] = {}
    for row in records(variants_df, exclude=("employer_id",)):
        title_norm = row.pop("title_norm")
        variants_by_title.setdefault(title_norm, []).append(TitleVariant(**row))

    top_positions = [
        TopPosition(**row, variants=variants_by_title.get(row["title_norm"], []))
        for row in records(positions_df, exclude=("employer_id", "year"))
    ]

    return EmployerProfile(
        employer_id=w["employer_id"], employer_name=w["employer_name"], sector_id=w["sector_id"],
        sector_name=w["sector_name"], subsector=w["subsector"], region=w["region"],
        municipality=w["municipality"], population=w["population"],
        first_year_present=w["first_year_present"], last_year_present=w["last_year_present"],
        years_present=w["years_present"], current=current, history=history,
        top_earners=top_earners, top_positions=top_positions,
    )


if __name__ == "__main__":
    import json

    ids = query("SELECT employer_id FROM employer_wide ORDER BY current_headcount DESC LIMIT 5")["employer_id"].tolist()
    for eid in ids:
        p = get_employer_profile(eid)
        assert p is not None
        payload = p.model_dump_json()
        json.loads(payload)
        print(f"  {eid}: {p.employer_name} — {len(p.history)} yrs, {len(p.top_earners)} top earners, "
              f"{len(p.top_positions)} top positions, {len(payload)} bytes, OK")

    print(f"unknown id -> {get_employer_profile('not-a-real-id')!r}")
