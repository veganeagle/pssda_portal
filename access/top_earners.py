"""Top Earners leaderboard: filterable by sector, employer (name-contains),
position (sector_id + title_norm together — a bare title spans domains, same
rule as everywhere else), and year. No year filter = the dataset's latest
year. Ranks are computed within each year's own population (pipeline/
rankings.py), never mixed across years.
"""
from __future__ import annotations

from access._rows import records
from access.db import query
from models.top_earners import TopEarnerRow

DEFAULT_LIMIT = 100


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_available_years() -> list[int]:
    df = query("SELECT DISTINCT year FROM top_earners_history ORDER BY year DESC")
    return [int(y) for y in df["year"]]


def search_top_earners(
    sector_id: str | None = None, employer_contains: str | None = None,
    title_norm: str | None = None, year: int | None = None, limit: int = DEFAULT_LIMIT,
) -> list[TopEarnerRow]:
    conditions = []
    params: list = []

    if year is None:
        conditions.append("year = (SELECT MAX(year) FROM top_earners_history)")
    else:
        conditions.append("year = ?")
        params.append(year)

    if sector_id:
        conditions.append("sector_id = ?")
        params.append(sector_id)
    if employer_contains:
        conditions.append("LOWER(employer_name) LIKE LOWER(?) ESCAPE '\\'")
        params.append(f"%{_escape_like(employer_contains)}%")
    if title_norm:
        conditions.append("title_norm = ?")
        params.append(title_norm)

    where_clause = f"WHERE {' AND '.join(conditions)}"
    sql = f"""
        SELECT * FROM top_earners_history
        {where_clause}
        ORDER BY total_comp DESC
        LIMIT ?
    """
    params.append(limit)
    df = query(sql, params)
    return [TopEarnerRow(**row) for row in records(df)]


if __name__ == "__main__":
    import time

    print("available years:", list_available_years())

    cases = [
        {},
        {"sector_id": "7"},
        {"employer_contains": "toronto"},
        {"sector_id": "8", "title_norm": "CONSTABLE"},
        {"sector_id": "8", "title_norm": "CONSTABLE", "employer_contains": "toronto"},
        {"year": 2020},
    ]
    for case in cases:
        start = time.perf_counter()
        rows = search_top_earners(**case, limit=10)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"{case} -> {len(rows)} rows in {elapsed:.1f}ms")
        for r in rows[:3]:
            print(f"    #{r.rank_province} province: {r.first_name} {r.last_name} — {r.job_title} @ {r.employer_name} — ${r.total_comp:,.0f}")
