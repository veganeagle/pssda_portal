"""The disclosure threshold and job pay against inflation. The $100,000 line
was set in 1996 and never indexed; here it is carried forward with Ontario's
CPI to show who would still be disclosed, and the most common jobs' same-person
pay change is compared with CPI over the same years.
"""
from __future__ import annotations

from functools import cache

from access._rows import records
from access.db import query

# Ontario all-items CPI, annual average, 2002=100 (Statistics Canada table 18-10-0005-01).
ONTARIO_CPI = {
    1996: 88.2, 2010: 116.5, 2011: 120.1, 2012: 121.8, 2013: 123.0, 2014: 125.9, 2015: 127.4, 2016: 129.7,
    2017: 131.9, 2018: 135.0, 2019: 137.5, 2020: 138.4, 2021: 143.2, 2022: 152.9, 2023: 158.7, 2024: 162.5,
    2025: 165.6,
}
THRESHOLD_YEAR = 1996
THRESHOLD = 100_000
JOB_COUNT = 12
WINDOWS = (2015, 2020)  # start years; each compared with the latest year
MIN_COMPARED = 30  # people in the job in both years


def indexed_threshold(year: int) -> float:
    return THRESHOLD * ONTARIO_CPI[year] / ONTARIO_CPI[THRESHOLD_YEAR]


def cpi_change(start: int, end: int) -> float:
    return ONTARIO_CPI[end] / ONTARIO_CPI[start] - 1


@cache
def threshold_by_year() -> list[dict]:
    """Per year: everyone disclosed, and how many earned at least the 1996
    threshold carried forward with inflation."""
    values = ", ".join(f"({y}, {indexed_threshold(y)})" for y in ONTARIO_CPI if y != THRESHOLD_YEAR)
    return records(query(f"""
        WITH th(year, threshold) AS (VALUES {values})
        SELECT t.year, ANY_VALUE(th.threshold) AS threshold, COUNT(*)::INTEGER AS disclosed,
               COUNT(*) FILTER (WHERE t.salary_paid >= th.threshold)::INTEGER AS above
        FROM top_earners_history t JOIN th USING (year)
        GROUP BY t.year ORDER BY t.year
    """))


@cache
def sectors_vs_threshold() -> list[dict]:
    """Latest year, per sector: everyone disclosed and those at or over the
    indexed threshold, with each sector's share of both lists."""
    year = max(ONTARIO_CPI)
    rows = records(query("""
        SELECT sector_id, ANY_VALUE(sector_name) AS sector_name, COUNT(*)::INTEGER AS disclosed,
               COUNT(*) FILTER (WHERE salary_paid >= ?)::INTEGER AS above
        FROM top_earners_history WHERE year = ? AND sector_id NOT IN ('-1', '99')
        GROUP BY sector_id ORDER BY disclosed DESC
    """, [indexed_threshold(year), year]))
    total, total_above = sum(r["disclosed"] for r in rows), sum(r["above"] for r in rows)
    return [r | {"share": r["disclosed"] / total, "share_above": r["above"] / total_above,
                 "pct_kept": r["above"] / r["disclosed"]} for r in rows]


@cache
def jobs_vs_inflation() -> dict:
    """The most common jobs in the latest year. For each window, the median
    ratio of a person's salary in the latest year to their salary in the start
    year, for people in the same job (sector + Title_Norm) in both years; then
    that change net of CPI over the same years."""
    end = max(ONTARIO_CPI)
    jobs = records(query("""
        SELECT sector_id, title_norm, headcount, median_salary FROM position_history
        WHERE year = ? ORDER BY headcount DESC LIMIT ?
    """, [end, JOB_COUNT]))
    names = dict(query("SELECT DISTINCT sector_id, sector_name FROM employee_history").itertuples(index=False))
    changes = {}
    for start in WINDOWS:
        for r in records(query("""
            WITH s AS (SELECT employee_id, sector_id, title_norm, salary_paid FROM employee_history WHERE year = ?),
                 e AS (SELECT employee_id, sector_id, title_norm, salary_paid FROM employee_history WHERE year = ?)
            SELECT e.sector_id, e.title_norm, COUNT(*)::INTEGER AS n, MEDIAN(e.salary_paid / s.salary_paid) - 1 AS change
            FROM e JOIN s USING (employee_id, sector_id, title_norm)
            WHERE e.title_norm IS NOT NULL GROUP BY ALL
        """, [start, end])):
            changes[(start, r["sector_id"], r["title_norm"])] = r
    windows = [{"start": start, "end": end, "cpi": cpi_change(start, end)} for start in WINDOWS]
    for j in jobs:
        j["sector_name"] = names.get(j["sector_id"])
        j["windows"] = []
        for w in windows:
            c = changes.get((w["start"], j["sector_id"], j["title_norm"]))
            ok = c is not None and c["n"] >= MIN_COMPARED
            j["windows"].append({
                "n": c["n"] if c else 0, "enough": ok,
                "change": c["change"] if ok else None,
                "real": (1 + c["change"]) / (1 + w["cpi"]) - 1 if ok else None,
            })
    return {"end": end, "windows": windows, "jobs": jobs}


if __name__ == "__main__":
    for r in threshold_by_year():
        print(r["year"], round(r["threshold"]), r["disclosed"], r["above"])
    d = jobs_vs_inflation()
    print([(w["start"], round(w["cpi"], 3)) for w in d["windows"]])
    for j in d["jobs"]:
        print(j["title_norm"], j["sector_name"], [(w["n"], w["change"] and round(w["change"], 3), w["real"] and round(w["real"], 3)) for w in j["windows"]])
