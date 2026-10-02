"""Search over employee_wide/employee_history: first/last/middle name (prefix match),
current sector (exact), employer/title (contains, matched against any year in
history), year present. Returns lightweight summaries — call get_employee_profile()
for the full record.
"""
from __future__ import annotations

from access.db import query
from models.employee_profile import EmployeeSearchResult, SearchOutcome, SectorOption

RESULT_CAP = 100


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_sectors() -> list[SectorOption]:
    df = query("SELECT sector_id, sector_name FROM sectors ORDER BY sector_name")
    return [SectorOption(**row) for row in df.to_dict(orient="records")]


def search_employees(
    first: str | None = None, last: str | None = None, middle: str | None = None,
    sector: str | None = None, employer_contains: str | None = None,
    title_contains: str | None = None, year: int | None = None,
) -> SearchOutcome:
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

    if not conditions:
        return SearchOutcome(results=[], too_many=False)  # no open "browse everyone"

    sql = f"""
        SELECT employee_id, first_name, last_name, middle,
               current_employer_name, current_job_title, first_seen_year, last_seen_year
        FROM employee_wide w
        WHERE {" AND ".join(conditions)}
        ORDER BY last_seen_year DESC, first_seen_year ASC
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
