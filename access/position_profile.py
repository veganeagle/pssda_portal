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
    title_contains: str | None = None, sector_id: str | None = None, employer_id: str | None = None,
    limit: int = SEARCH_LIMIT,
) -> list[PositionSearchResult]:
    """employer_id scopes to one employer's own positions (employer_position_wide)
    instead of the province/sector-wide aggregate (position_wide) — same two
    tables, same shape of columns, so this is a straight swap, not two code
    paths. employer_id is never user-controlled free text (always a picked
    option value), but it's still bound as a parameter like everything else.
    """
    conditions = []
    params: list = []
    if title_contains:
        conditions.append("LOWER(title_norm) LIKE LOWER(?) ESCAPE '\\'")
        params.append(f"%{_escape_like(title_contains)}%")
    if sector_id:
        conditions.append("sector_id = ?")
        params.append(sector_id)
    if employer_id:
        conditions.append("employer_id = ?")
        params.append(employer_id)

    table = "employer_position_wide" if employer_id else "position_wide"
    employer_cols = ", employer_id, employer_name" if employer_id else ""
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT sector_id, title_norm, sector_name, current_year,
               current_headcount, current_avg_total_comp{employer_cols}
        FROM {table}
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


def sector_position_overview() -> list[dict]:
    """One row per sector — disclosed employees, how many of them hold a
    normalized ("mapped") title, how many distinct normalized positions
    exist, and the single most common one — for the "positions by sector"
    table on the search page. Both sides are pinned to the same year (the
    dataset's actual latest year) since position_wide's own "current" year
    is tracked per-position and can lag for a role that went stale — see
    access.sector_profile's top_positions query for the same fix. Excludes
    the sentinel sectors (-1 unknown, 99 seconded) just like the sector
    picker does.
    """
    df = query("""
        WITH cy AS (SELECT MAX(year) AS y FROM employer_history),
        totals AS (
            SELECT w.sector_id, w.sector_name, SUM(h.headcount)::BIGINT AS total_headcount
            FROM employer_history h JOIN employer_wide w ON w.employer_id = h.employer_id
            WHERE h.year = (SELECT y FROM cy) AND w.sector_id NOT IN ('-1', '99')
            GROUP BY w.sector_id, w.sector_name
        ), normed AS (
            SELECT sector_id, SUM(current_headcount)::BIGINT AS normed_headcount,
                   COUNT(DISTINCT title_norm) AS n_positions
            FROM position_wide
            WHERE current_year = (SELECT y FROM cy) AND title_norm IS NOT NULL
            GROUP BY sector_id
        ), top_role AS (
            SELECT sector_id, title_norm, current_headcount AS headcount,
                   ROW_NUMBER() OVER (PARTITION BY sector_id ORDER BY current_headcount DESC) AS rn
            FROM position_wide WHERE current_year = (SELECT y FROM cy) AND title_norm IS NOT NULL
        )
        SELECT t.sector_id, t.sector_name, t.total_headcount,
               COALESCE(n.n_positions, 0) AS n_positions,
               COALESCE(n.normed_headcount, 0) AS normed_headcount,
               r.title_norm AS top_role_title, r.headcount AS top_role_headcount
        FROM totals t
        LEFT JOIN normed n ON n.sector_id = t.sector_id
        LEFT JOIN top_role r ON r.sector_id = t.sector_id AND r.rn = 1
        ORDER BY t.total_headcount DESC
    """)
    return records(df)


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
