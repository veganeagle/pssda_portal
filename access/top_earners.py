"""Top Earners leaderboard: filterable by sector, employer (name-contains),
position (sector_id + title_norm together — a bare title spans domains, same
rule as everywhere else), and year. No year filter = the dataset's latest
year. Ranks are computed within each year's own population (pipeline/
rankings.py), never mixed across years.
"""
from __future__ import annotations

from functools import cache, lru_cache

from access._rows import records
from access.db import query
from models.top_earners import TopEarnerRow

DEFAULT_LIMIT = 100


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_available_years() -> list[int]:
    df = query("SELECT DISTINCT year FROM top_earners_history ORDER BY year DESC")
    return [int(y) for y in df["year"]]


TOP_N_PROVINCE = 1000


# Memoized per process: cube data only changes on a refresh, which restarts the app.
@cache
def sector_top_earners_overview() -> list[dict]:
    """One row per sector, current year only — disclosed employees, how many
    of them land in the province-wide top 1000 by total comp, the sector's
    P90 salary, and its single highest-paid person — for the "top earners by
    sector" table on the search page. Excludes the sentinel sectors (-1
    unknown, 99 seconded) just like the sector picker does.
    """
    df = query("""
        WITH cy AS (SELECT MAX(year) AS y FROM top_earners_history),
        base AS (SELECT * FROM top_earners_history WHERE year = (SELECT y FROM cy)),
        totals AS (
            SELECT sector_id, sector_name, COUNT(*) AS n_employees,
                   SUM(CASE WHEN rank_province <= ? THEN 1 ELSE 0 END)::INTEGER AS n_in_top_province,
                   PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY salary_paid) AS p90_salary
            FROM base WHERE sector_id NOT IN ('-1', '99')
            GROUP BY sector_id, sector_name
        ), top1 AS (
            SELECT sector_id, employee_id, first_name, last_name, employer_id, employer_name, total_comp,
                   ROW_NUMBER() OVER (PARTITION BY sector_id ORDER BY total_comp DESC) AS rn
            FROM base WHERE sector_id NOT IN ('-1', '99')
        )
        SELECT t.sector_id, t.sector_name, t.n_employees, t.n_in_top_province, t.p90_salary,
               r.employee_id AS top_employee_id, r.first_name AS top_first_name, r.last_name AS top_last_name,
               r.employer_id AS top_employer_id, r.employer_name AS top_employer_name, r.total_comp AS top_total_comp
        FROM totals t
        LEFT JOIN top1 r ON r.sector_id = t.sector_id AND r.rn = 1
        ORDER BY t.n_in_top_province DESC
    """, [TOP_N_PROVINCE])
    return records(df)


@lru_cache(maxsize=256)
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


# ---- sector view (Top Earners with a sector selected) ----

HIGH_EARNER_THRESHOLD = 250_000   # total comp; nominal dollars, like the $100K line itself
HIGH_EARNER_TREND_YEARS = 5
INCREASES_LIMIT = 10


@lru_cache(maxsize=128)
def sector_high_earner_trend(sector_id: str, end_year: int) -> list[dict]:
    """People in the sector at or above HIGH_EARNER_THRESHOLD total comp, for
    the HIGH_EARNER_TREND_YEARS years ending at end_year."""
    df = query("""
        SELECT year, COUNT(*) FILTER (WHERE total_comp >= ?)::INTEGER AS n
        FROM top_earners_history
        WHERE sector_id = ? AND year BETWEEN ? AND ?
        GROUP BY year ORDER BY year
    """, [HIGH_EARNER_THRESHOLD, sector_id, end_year - HIGH_EARNER_TREND_YEARS + 1, end_year])
    return records(df)


@lru_cache(maxsize=256)
def sector_biggest_increases(sector_id: str, year: int, include_employer_changes: bool = False) -> list[dict]:
    """Largest year-over-year dollar increases in total comp, for people in the
    sector this year who were also disclosed the year before. By default both
    years must be at the same employer — that drops employer moves and most
    record-linking errors (two different people with one name). Big jumps can
    still be a partial prior year, retroactive or one-time pay, not a raise."""
    df = query("""
        WITH cur AS (
            SELECT employee_id, first_name, last_name, employer_id, employer_name, job_title, total_comp
            FROM top_earners_history WHERE year = ? AND sector_id = ?
        ), prev AS (
            SELECT employee_id, employer_id AS prior_employer_id, total_comp AS prior_total_comp
            FROM top_earners_history WHERE year = ?
        )
        SELECT cur.*, prev.prior_total_comp,
               cur.total_comp - prev.prior_total_comp AS increase,
               cur.total_comp / prev.prior_total_comp - 1 AS pct_increase
        FROM cur JOIN prev USING (employee_id)
        WHERE ? OR cur.employer_id = prev.prior_employer_id
        ORDER BY increase DESC
        LIMIT ?
    """, [year, sector_id, year - 1, include_employer_changes, INCREASES_LIMIT])
    return records(df)
