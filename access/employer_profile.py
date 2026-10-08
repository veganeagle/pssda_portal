"""Single-employer lookup: EmployerID -> EmployerProfile."""
from __future__ import annotations

from functools import lru_cache
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


def list_employers_for_filter(active_only: bool = True) -> list[dict]:
    """Every employer, lightweight — id/name/sector only — for the Employee
    search page's sector-cascading employer picker. active_only=True (the
    default, matching that page's own "Active only" default) excludes
    employers whose last disclosure year is before the dataset's current
    year — e.g. an office dissolved or folded into another ministry still
    has a row here (so its own profile page still resolves), but offering
    it in an "active" picker is a dead end: no one currently disclosed can
    match it, so picking it always returns zero results.
    """
    where = "WHERE current_year = (SELECT MAX(current_year) FROM employer_wide)" if active_only else ""
    df = query(f"SELECT employer_id, employer_name, sector_id FROM employer_wide {where} ORDER BY employer_name")
    return records(df)


def sector_employer_overview() -> list[dict]:
    """One row per sector — employer count, total headcount represented,
    median employer size, and the sector's single largest employer (by
    current headcount) — for the "employers by sector" table on the search
    page. Excludes the sentinel sectors (-1 unknown, 99 seconded) just like
    the sector picker does.
    """
    df = query("""
        WITH base AS (
            SELECT sector_id, sector_name, employer_id, employer_name, current_headcount
            FROM employer_wide WHERE sector_id NOT IN ('-1', '99')
        ), agg AS (
            SELECT sector_id, sector_name, COUNT(*) AS employer_count,
                   SUM(current_headcount)::BIGINT AS total_headcount,
                   ROUND(MEDIAN(current_headcount))::INTEGER AS median_employer_size
            FROM base GROUP BY sector_id, sector_name
        ), largest AS (
            SELECT sector_id, employer_id, employer_name, current_headcount,
                   ROW_NUMBER() OVER (PARTITION BY sector_id ORDER BY current_headcount DESC) AS rn
            FROM base
        )
        SELECT a.sector_id, a.sector_name, a.employer_count, a.total_headcount, a.median_employer_size,
               l.employer_id AS largest_employer_id, l.employer_name AS largest_employer_name,
               l.current_headcount AS largest_headcount
        FROM agg a JOIN largest l ON l.sector_id = a.sector_id AND l.rn = 1
        ORDER BY a.total_headcount DESC
    """)
    return records(df)


# A sector's fastest-growing employers, by year-over-year change in disclosed
# employees. Small bases swing wildly (2 -> 5 people is +150%), so an employer
# needs at least this many disclosed employees in the prior year to be ranked.
GROWTH_MIN_PRIOR_HEADCOUNT = 25
SECTOR_MIX_TOP_N = 5


# Memoized per process: cube data only changes on a refresh, which restarts the app.
@lru_cache(maxsize=32)
def sector_employer_growth(sector_id: str, limit: int = 5) -> list[dict]:
    df = query("""
        WITH yr AS (SELECT MAX(year) AS y FROM employer_history),
             cur AS (SELECT h.employer_id, h.headcount FROM employer_history h, yr WHERE h.year = yr.y),
             prev AS (SELECT h.employer_id, h.headcount FROM employer_history h, yr WHERE h.year = yr.y - 1)
        SELECT w.employer_id, w.employer_name, prev.headcount AS prior_headcount, cur.headcount AS headcount,
               cur.headcount::DOUBLE / prev.headcount - 1 AS growth
        FROM employer_wide w JOIN cur USING (employer_id) JOIN prev USING (employer_id)
        WHERE w.sector_id = ? AND prev.headcount >= ?
        ORDER BY growth DESC
        LIMIT ?
    """, [sector_id, GROWTH_MIN_PRIOR_HEADCOUNT, limit])
    return records(df)


@lru_cache(maxsize=32)
def sector_employer_mix(sector_id: str) -> list[dict]:
    """Current-year disclosed employees in a sector: the SECTOR_MIX_TOP_N
    largest employers individually, everyone else rolled into one row."""
    df = query("""
        SELECT employer_id, employer_name, current_headcount AS headcount
        FROM employer_wide
        WHERE sector_id = ? AND current_year = (SELECT MAX(current_year) FROM employer_wide)
        ORDER BY current_headcount DESC
    """, [sector_id])
    rows = records(df)
    top, rest = rows[:SECTOR_MIX_TOP_N], rows[SECTOR_MIX_TOP_N:]
    if rest:
        top.append({"employer_id": None, "employer_name": None, "headcount": sum(r["headcount"] for r in rest),
                    "n_employers": len(rest)})
    return top


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
