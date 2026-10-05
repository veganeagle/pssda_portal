"""Search over employee_wide/employee_history: first/last/middle name (prefix match),
current sector (exact), employer/title (contains, matched against any year in
history), year present. Returns lightweight summaries — call get_employee_profile()
for the full record.
"""
from __future__ import annotations

from functools import cache

from access._rows import records
from access.db import query
from models.employee_profile import EmployeeSearchResult, SearchOutcome, SectorOption

RESULT_CAP = 100  # unscoped/fuzzy search: blocks with too_many past this, no escape hatch
ENTITY_PAGE_SIZE = 100  # page size once an employer-scoped search needs pagination
ENTITY_FULL_THRESHOLD = 500  # at or under this, return every row in one go instead of paginating
GENDER_MIN_GROUP_SIZE = 20  # matches pipeline/gender.py's own floor

_RESULT_COLUMNS = (
    "employee_id, first_name, last_name, middle, current_employer_name, "
    "current_job_title, current_total_comp, first_seen_year, last_seen_year"
)
_RESULT_ORDER = "ORDER BY last_name ASC, first_name ASC, last_seen_year DESC, first_seen_year ASC"


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_sectors() -> list[SectorOption]:
    # Excludes the sentinel sectors (-1 unknown, 99 seconded) from every
    # sector filter dropdown site-wide, same as the home/sector picker's own
    # list_sectors_for_picker() — "SECONDED" showing up as a real sector
    # option was a real inconsistency, not a deliberate choice.
    df = query("SELECT sector_id, sector_name FROM sectors WHERE sector_id NOT IN ('-1', '99') ORDER BY sector_name")
    return [SectorOption(**row) for row in df.to_dict(orient="records")]


# Memoized per process: cube data only changes on a refresh, which restarts the app.
@cache
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


def _build_conditions(
    first, last, middle, sector, employer_contains, title_contains, year,
    include_inactive, employer_id, position,
) -> tuple[list[str], list]:
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

    if conditions and not include_inactive:
        conditions.append("w.last_seen_year = (SELECT MAX(last_seen_year) FROM employee_wide)")

    return conditions, params


def search_employees(
    first: str | None = None, last: str | None = None, middle: str | None = None,
    sector: str | None = None, employer_contains: str | None = None,
    title_contains: str | None = None, year: int | None = None,
    include_inactive: bool = False,
    employer_id: str | None = None, position: tuple[str, str] | None = None,
    page: int = 1,
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

    An employer_id search is bounded by that employer's own (known, already
    displayed elsewhere) headcount, so instead of the unscoped case's "too
    many, narrow your search" wall, it returns everything when that's small
    (ENTITY_FULL_THRESHOLD) or paginates when it isn't — never a dead end.
    """
    conditions, params = _build_conditions(
        first, last, middle, sector, employer_contains, title_contains, year,
        include_inactive, employer_id, position,
    )
    if not conditions:
        return SearchOutcome(results=[], too_many=False)  # no open "browse everyone"

    base_from = f"FROM employee_wide w WHERE {' AND '.join(conditions)}"

    if not employer_id:
        sql = f"SELECT {_RESULT_COLUMNS} {base_from} {_RESULT_ORDER} LIMIT ?"
        df = query(sql, params + [RESULT_CAP + 1])  # peek one past the cap in one query
        if len(df) > RESULT_CAP:
            return SearchOutcome(results=[], too_many=True)
        return SearchOutcome(
            results=[EmployeeSearchResult(**row) for row in df.to_dict(orient="records")], too_many=False
        )

    total = int(query(f"SELECT COUNT(*) AS n {base_from}", params).iloc[0]["n"])

    if total <= ENTITY_FULL_THRESHOLD:
        df = query(f"SELECT {_RESULT_COLUMNS} {base_from} {_RESULT_ORDER}", params)
        return SearchOutcome(
            results=[EmployeeSearchResult(**row) for row in df.to_dict(orient="records")],
            too_many=False, total_count=total, page=1, page_size=None,
        )

    page = max(1, page)
    offset = (page - 1) * ENTITY_PAGE_SIZE
    df = query(f"SELECT {_RESULT_COLUMNS} {base_from} {_RESULT_ORDER} LIMIT ? OFFSET ?", params + [ENTITY_PAGE_SIZE, offset])
    return SearchOutcome(
        results=[EmployeeSearchResult(**row) for row in df.to_dict(orient="records")],
        too_many=False, total_count=total, page=page, page_size=ENTITY_PAGE_SIZE,
    )


def search_employees_all(
    first: str | None = None, last: str | None = None, middle: str | None = None,
    sector: str | None = None, year: int | None = None, include_inactive: bool = False,
    employer_id: str | None = None, position: tuple[str, str] | None = None,
) -> list[EmployeeSearchResult]:
    """Every matching row, no cap — backs the rate-limited CSV export for an
    employer-scoped search once it's past ENTITY_FULL_THRESHOLD (below that,
    search_employees() already returns everything). employer_id is required:
    there's no size bound to justify an unlimited fetch without it.
    """
    if not employer_id:
        raise ValueError("search_employees_all requires employer_id")
    conditions, params = _build_conditions(
        first, last, middle, sector, None, None, year, include_inactive, employer_id, position,
    )
    sql = f"SELECT {_RESULT_COLUMNS} FROM employee_wide w WHERE {' AND '.join(conditions)} {_RESULT_ORDER}"
    df = query(sql, params)
    return [EmployeeSearchResult(**row) for row in df.to_dict(orient="records")]


if __name__ == "__main__":
    import time

    cases = [
        {"last": "sm", "employer_contains": "toronto"},
        {"title_contains": "constable", "year": 2020},
        {"employer_contains": "police", "title_contains": "sergeant", "year": 2015},
        {"first": "j", "last": "smith"},
        {"last": "a"},  # expect too_many
        {"employer_id": "10_0060"},  # small employer (<=500) -> full list, no pagination
        {"employer_id": "10_0013"},  # TDSB (14,085) -> paginated, page 1
        {"employer_id": "10_0013", "page": 2},  # TDSB page 2
    ]
    for case in cases:
        start = time.perf_counter()
        outcome = search_employees(**case)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"{case} -> too_many={outcome.too_many}, total_count={outcome.total_count}, "
              f"page={outcome.page}, page_size={outcome.page_size}, {len(outcome.results)} results in {elapsed:.1f}ms")
        for r in outcome.results[:3]:
            print(f"    {r.employee_id}: {r.first_name} {r.last_name} — {r.current_job_title} @ {r.current_employer_name}")

    all_rows = search_employees_all(employer_id="10_0013")
    print(f"search_employees_all(TDSB) -> {len(all_rows)} rows")

    print(f"sectors: {[s.sector_name for s in list_sectors()]}")
