"""Single-position lookup: (sector_id, title_norm) -> PositionProfile. Positions are
scoped to a sector because a bare title spans unrelated domains (see pipeline docstring).
"""
from __future__ import annotations

from typing import Optional

from access._rows import records
from access.db import query
from models.position_profile import (
    PositionEmployerRank,
    PositionOption,
    PositionProfile,
    PositionSearchResult,
    PositionYearRecord,
)

SEARCH_LIMIT = 50


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_positions(
    title_contains: str | None = None, sector_id: str | None = None, limit: int = SEARCH_LIMIT
) -> list[PositionSearchResult]:
    conditions = []
    params: list = []
    if title_contains:
        conditions.append("LOWER(title_norm) LIKE LOWER(?) ESCAPE '\\'")
        params.append(f"%{_escape_like(title_contains)}%")
    if sector_id:
        conditions.append("sector_id = ?")
        params.append(sector_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT sector_id, title_norm, sector_name, current_year,
               current_headcount, current_avg_total_comp
        FROM position_wide
        {where_clause}
        ORDER BY current_headcount DESC
        LIMIT ?
    """
    params.append(limit)
    df = query(sql, params)
    return [PositionSearchResult(**row) for row in records(df)]


def list_positions() -> list[PositionOption]:
    df = query(
        "SELECT sector_id, title_norm, sector_name FROM position_wide ORDER BY sector_name, title_norm"
    )
    return [PositionOption(**row) for row in records(df)]


def get_position_profile(sector_id: str, title_norm: str) -> Optional[PositionProfile]:
    wide = query(
        "SELECT * FROM position_wide WHERE sector_id = ? AND title_norm = ?", [sector_id, title_norm]
    )
    if wide.empty:
        return None
    w = records(wide)[0]

    history_df = query(
        "SELECT * FROM position_history WHERE sector_id = ? AND title_norm = ? ORDER BY year DESC",
        [sector_id, title_norm],
    )
    history = [PositionYearRecord(**row) for row in records(history_df, exclude=("sector_id", "title_norm"))]
    current = next((h for h in history if h.year == w["current_year"]), history[-1])

    by_employer_df = query(
        "SELECT * FROM position_by_employer WHERE sector_id = ? AND title_norm = ? ORDER BY rank",
        [sector_id, title_norm],
    )
    by_employer = [
        PositionEmployerRank(**row) for row in records(by_employer_df, exclude=("sector_id", "title_norm", "year"))
    ]

    return PositionProfile(
        sector_id=w["sector_id"], title_norm=w["title_norm"], sector_name=w["sector_name"],
        first_year_present=w["first_year_present"], last_year_present=w["last_year_present"],
        years_present=w["years_present"], current=current, history=history, by_employer=by_employer,
    )


if __name__ == "__main__":
    import json

    rows = query(
        "SELECT sector_id, title_norm FROM position_wide ORDER BY current_headcount DESC LIMIT 5"
    ).to_dict(orient="records")
    for r in rows:
        p = get_position_profile(r["sector_id"], r["title_norm"])
        assert p is not None
        payload = p.model_dump_json()
        json.loads(payload)
        print(f"  {r['sector_id']}/{r['title_norm']}: {len(p.history)} yrs, {len(p.by_employer)} employers, {len(payload)} bytes, OK")

    print(f"unknown -> {get_position_profile('99', 'NOT A ROLE')!r}")
