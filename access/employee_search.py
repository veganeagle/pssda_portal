"""Search over employee_wide/employee_history: first/last/middle name (prefix match),
current sector (exact), employer/title (contains, matched against any year in
history), year present. Returns lightweight summaries — call get_employee_profile()
for the full record.
"""
from __future__ import annotations

from access._rows import records
from access.db import query
from models.employee_profile import EmployeeSearchResult, SearchOutcome, SectorOption

RESULT_CAP = 100
GENDER_MIN_GROUP_SIZE = 20  # matches pipeline/gender.py's own floor


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_sectors() -> list[SectorOption]:
    # Excludes the sentinel sectors (-1 unknown, 99 seconded) from every
    # sector filter dropdown site-wide, same as the home/sector picker's own
    # list_sectors_for_picker() — "SECONDED" showing up as a real sector
    # option was a real inconsistency, not a deliberate choice.
    df = query("SELECT sector_id, sector_name FROM sectors WHERE sector_id NOT IN ('-1', '99') ORDER BY sector_name")
    return [SectorOption(**row) for row in df.to_dict(orient="records")]


def sector_population_overview() -> list[dict]:
    """One row per sector — the active (most-recent-year) disclosed
    population, how many are new this year (first ever appearance on the
    list, not just new to this employer), estimated % female, and
    year-over-year attrition (disclosed last year but not this year — note
    that's "no longer disclosed," which includes genuine departures but also
    anyone who simply dipped below the $100,000 threshold while staying
    employed, same caveat as "newly disclosed" elsewhere on the site).
    Excludes the sentinel sectors (-1 unknown, 99 seconded).
    """
    df = query("""
        WITH cy AS (SELECT MAX(last_seen_year) AS y FROM employee_wide),
        active AS (SELECT * FROM employee_wide WHERE last_seen_year = (SELECT y FROM cy)),
        totals AS (
            SELECT current_sector_id AS sector_id, current_sector_name AS sector_name,
                   COUNT(*) AS n_employees,
                   SUM(CASE WHEN first_seen_year = (SELECT y FROM cy) THEN 1 ELSE 0 END)::INTEGER AS n_new,
                   CASE WHEN COUNT(*) >= ? THEN ROUND(AVG(CASE WHEN prob_female >= 0.5 THEN 1.0 ELSE 0.0 END) * 100, 1) END AS pct_female
            FROM active WHERE current_sector_id NOT IN ('-1', '99')
            GROUP BY current_sector_id, current_sector_name
        ), prior AS (
            SELECT employee_id, sector_id FROM employee_history
            WHERE year = (SELECT y FROM cy) - 1 AND sector_id NOT IN ('-1', '99')
        ), current_ids AS (
            SELECT DISTINCT employee_id FROM employee_history WHERE year = (SELECT y FROM cy)
        ), attrition AS (
            SELECT prior.sector_id,
                   COUNT(*)::INTEGER AS n_prior_year,
                   SUM(CASE WHEN current_ids.employee_id IS NULL THEN 1 ELSE 0 END)::INTEGER AS n_attrition
            FROM prior LEFT JOIN current_ids USING (employee_id)
            GROUP BY prior.sector_id
        )
        SELECT t.sector_id, t.sector_name, t.n_employees, t.n_new, t.pct_female,
               COALESCE(a.n_prior_year, 0) AS n_prior_year, COALESCE(a.n_attrition, 0) AS n_attrition
        FROM totals t LEFT JOIN attrition a ON a.sector_id = t.sector_id
        ORDER BY t.n_employees DESC
    """, [GENDER_MIN_GROUP_SIZE])
    return records(df)


def search_employees(
    first: str | None = None, last: str | None = None, middle: str | None = None,
    sector: str | None = None, employer_contains: str | None = None,
    title_contains: str | None = None, year: int | None = None,
    include_inactive: bool = False,
    employer_id: str | None = None, position: tuple[str, str] | None = None,
) -> SearchOutcome:
    """employer_id and position scope the search to the people *currently*
    (most-recent-year) at that employer and/or in that (sector_id,
    title_norm) position — an exact-ID match against their current record,
    unlike employer_contains/title_contains which are fuzzy text search over
    anyone's entire history. Matching current-only (not "ever held this
    role") keeps results consistent with what the employer/position/combo
    profile pages themselves show, and avoids surfacing someone whose
    current, unrelated job happens to share a long-past history row. Used by
    the mini search box on those pages; never exposed as free text, so no
    injection surface.
    """
    conditions = []
    params: list = []

    for col, val in (("first_name", first), ("last_name", last), ("middle", middle)):
        if val:
            conditions.append(f"LOWER(w.{col}) LIKE LOWER(?) ESCAPE '\\'")
            params.append(f"{_escape_like(val)}%")

    if sector:
        conditions.append("w.current_sector_id = ?")
        params.append(sector)

    if employer_contains:
        conditions.append(
            "EXISTS (SELECT 1 FROM employee_history h WHERE h.employee_id = w.employee_id "
            "AND LOWER(h.employer_name) LIKE LOWER(?) ESCAPE '\\')"
        )
        params.append(f"%{_escape_like(employer_contains)}%")

    if title_contains:
        conditions.append(
            "EXISTS (SELECT 1 FROM employee_history h WHERE h.employee_id = w.employee_id "
            "AND (LOWER(h.job_title) LIKE LOWER(?) ESCAPE '\\' OR LOWER(h.title_norm) LIKE LOWER(?) ESCAPE '\\'))"
        )
        params.extend([f"%{_escape_like(title_contains)}%"] * 2)

    if year is not None:
        conditions.append(
            "EXISTS (SELECT 1 FROM employee_history h WHERE h.employee_id = w.employee_id AND h.year = ?)"
        )
        params.append(year)

    if employer_id:
        conditions.append("w.current_employer_id = ?")
        params.append(employer_id)

    if position:
        pos_sector_id, pos_title_norm = position
        conditions.append("w.current_sector_id = ? AND w.current_title_norm = ?")
        params.extend([pos_sector_id, pos_title_norm])

    if not conditions:
        return SearchOutcome(results=[], too_many=False)  # no open "browse everyone"

    if not include_inactive:
        conditions.append("w.last_seen_year = (SELECT MAX(last_seen_year) FROM employee_wide)")

    sql = f"""
        SELECT employee_id, first_name, last_name, middle,
               current_employer_name, current_job_title, current_total_comp,
               first_seen_year, last_seen_year
        FROM employee_wide w
        WHERE {" AND ".join(conditions)}
        ORDER BY last_name ASC, first_name ASC, last_seen_year DESC, first_seen_year ASC
        LIMIT ?
    """
    params.append(RESULT_CAP + 1)  # peek one past the cap to detect "too many" in one query
    df = query(sql, params)
    if len(df) > RESULT_CAP:
        return SearchOutcome(results=[], too_many=True)
    return SearchOutcome(
        results=[EmployeeSearchResult(**row) for row in df.to_dict(orient="records")], too_many=False
    )


if __name__ == "__main__":
    import time

    cases = [
        {"last": "sm", "employer_contains": "toronto"},
        {"title_contains": "constable", "year": 2020},
        {"employer_contains": "police", "title_contains": "sergeant", "year": 2015},
        {"first": "j", "last": "smith"},
        {"last": "a"},  # expect too_many
    ]
    for case in cases:
        start = time.perf_counter()
        outcome = search_employees(**case)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"{case} -> too_many={outcome.too_many}, {len(outcome.results)} results in {elapsed:.1f}ms")
        for r in outcome.results[:3]:
            print(f"    {r.employee_id}: {r.first_name} {r.last_name} — {r.current_job_title} @ {r.current_employer_name}")

    print(f"sectors: {[s.sector_name for s in list_sectors()]}")
