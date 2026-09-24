"""Top Earners leaderboard: filterable by sector, employer (name-contains), and
position (sector_id + title_norm together — a bare title spans domains, same
rule as everywhere else). No filter = province-wide. Always the dataset's
latest year (the cube only has one).
"""
from __future__ import annotations

from access._rows import records
from access.db import query
from models.top_earners import TopEarnerRow

DEFAULT_LIMIT = 100


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_top_earners(
    sector_id: str | None = None, employer_contains: str | None = None,
    title_norm: str | None = None, limit: int = DEFAULT_LIMIT,
) -> list[TopEarnerRow]:
    conditions = []
    params: list = []

    if sector_id:
        conditions.append("sector_id = ?")
        params.append(sector_id)
    if employer_contains:
        conditions.append("LOWER(employer_name) LIKE LOWER(?) ESCAPE '\\'")
        params.append(f"%{_escape_like(employer_contains)}%")
    if title_norm:
        conditions.append("title_norm = ?")
        params.append(title_norm)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT * FROM top_earners_current
        {where_clause}
        ORDER BY total_comp DESC
        LIMIT ?
    """
    params.append(limit)
    df = query(sql, params)
    return [TopEarnerRow(**row) for row in records(df)]


if __name__ == "__main__":
    import time

    cases = [
        {},
        {"sector_id": "7"},
        {"employer_contains": "toronto"},
        {"sector_id": "8", "title_norm": "CONSTABLE"},
        {"sector_id": "8", "title_norm": "CONSTABLE", "employer_contains": "toronto"},
    ]
    for case in cases:
        start = time.perf_counter()
        rows = search_top_earners(**case, limit=10)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"{case} -> {len(rows)} rows in {elapsed:.1f}ms")
        for r in rows[:3]:
            print(f"    #{r.rank_province} province: {r.first_name} {r.last_name} — {r.job_title} @ {r.employer_name} — ${r.total_comp:,.0f}")
