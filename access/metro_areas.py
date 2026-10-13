"""Metro areas: Ontario's large municipal areas, each one or more census
divisions (employer_wide.geographic_area), so an upper-tier region is counted
with its cities and towns, and a single-tier city with its police, transit and
library boards. Municipalities sector only.
"""
from __future__ import annotations

from functools import cache

from access._rows import records
from access.db import query

# slug, display name, region, census divisions, 2021 Census population of those
# divisions (Statistics Canada table 98-10-0002-01).
AREAS = [
    ("toronto", "Toronto", "CENTRAL", ("TORONTO",), 2_794_356),
    ("peel", "Peel", "CENTRAL", ("PEEL",), 1_451_022),
    ("york", "York", "CENTRAL", ("YORK",), 1_173_334),
    ("ottawa", "Ottawa", "EAST", ("OTTAWA",), 1_017_449),
    ("durham", "Durham", "CENTRAL", ("DURHAM",), 696_992),
    ("halton", "Halton", "CENTRAL", ("HALTON",), 596_637),
    ("waterloo", "Waterloo Region", "WEST", ("WATERLOO",), 587_165),
    ("hamilton", "Hamilton", "WEST", ("HAMILTON",), 569_353),
    ("simcoe", "Simcoe–Barrie–Orillia", "CENTRAL", ("SIMCOE",), 533_169),
    ("london", "London–Middlesex", "WEST", ("MIDDLESEX",), 500_563),
    ("niagara", "Niagara", "WEST", ("NIAGARA",), 477_941),
    ("windsor", "Windsor–Essex", "WEST", ("ESSEX",), 422_860),
]
MUNICIPAL_SECTOR = "8"
ONTARIO_POPULATION = 14_223_942  # 2021 Census, same table

_AREA_VALUES = ", ".join(f"('{slug}', '{cd}')" for slug, _, _, cds, _ in AREAS for cd in cds)


@cache
def metro_overview() -> list[dict]:
    """Per area, latest year: employers, disclosed employees, total disclosed
    salary, median salary, largest employer, and disclosed employees by year."""
    cur = {r["slug"]: r for r in records(query(f"""
        WITH a(slug, geographic_area) AS (VALUES {_AREA_VALUES}),
        y AS (SELECT MAX(year) AS y FROM top_earners_history),
        e AS (SELECT w.*, a.slug FROM employer_wide w JOIN a USING (geographic_area)
              WHERE w.sector_id = ? AND w.current_year = (SELECT y FROM y)),
        med AS (SELECT e.slug, MEDIAN(t.salary_paid) AS median_salary
                FROM top_earners_history t JOIN e USING (employer_id)
                WHERE t.year = (SELECT y FROM y) GROUP BY e.slug)
        SELECT e.slug, (SELECT y FROM y) AS year, COUNT(*)::INTEGER AS employers,
               SUM(e.current_headcount)::INTEGER AS headcount, SUM(e.current_total_payroll) AS payroll,
               ARG_MAX(e.employer_name, e.current_headcount) AS largest_name,
               ARG_MAX(e.employer_id, e.current_headcount) AS largest_id,
               MAX(e.current_headcount)::INTEGER AS largest_headcount,
               ANY_VALUE(med.median_salary) AS median_salary
        FROM e JOIN med USING (slug) GROUP BY e.slug
    """, [MUNICIPAL_SECTOR]))}
    trend: dict[str, list] = {}
    for r in records(query(f"""
        WITH a(slug, geographic_area) AS (VALUES {_AREA_VALUES})
        SELECT a.slug, h.year, SUM(h.headcount)::INTEGER AS headcount
        FROM employer_history h JOIN employer_wide w USING (employer_id) JOIN a USING (geographic_area)
        WHERE w.sector_id = ? GROUP BY ALL ORDER BY a.slug, h.year
    """, [MUNICIPAL_SECTOR])):
        trend.setdefault(r["slug"], []).append({"year": r["year"], "headcount": r["headcount"]})
    return [
        cur[slug] | {"name": name, "region": region, "population": pop,
                     "per_10k": cur[slug]["headcount"] / pop * 10_000, "trend": trend[slug]}
        for slug, name, region, _, pop in AREAS
    ]


# ---- One metro area's page ----

# Curated benchmark jobs (Title_Norm, Municipalities sector), present in most
# metro areas. per_10k only where nearly everyone in the job earns $100K+, so
# the disclosed count is close to the real headcount.
BENCHMARK_ROLES = [
    ("CONSTABLE", True), ("SERGEANT", False), ("STAFF SERGEANT", False), ("DETECTIVE", False),
    ("POLICE OPERATOR", False), ("FIREFIGHTER", True), ("FIRE CAPTAIN", False),
    ("PRIMARY CARE PARAMEDIC", False), ("ADVANCED CARE PARAMEDIC", False), ("TRANSIT OPERATOR", False),
    ("PLANNER", False), ("PROJECT MANAGER", False),
    ("SENIOR FINANCIAL ANALYST", False),
]
MIN_BENCHMARK_N = 5  # below this an area's median is one or two people's pay

# (label, Title_Norm values); every incumbent in the area is listed.
LEADERSHIP_ROLES = [
    ("Chief administrative officer", ("CAO", "CITY MANAGER")),
    ("Police chief", ("POLICE CHIEF",)),
    ("Deputy police chief", ("DEPUTY POLICE CHIEF",)),
    ("Fire chief", ("FIRE CHIEF",)),
    ("Paramedic chief", ("PARAMEDIC CHIEF",)),
    ("Medical officer of health", ("MEDICAL OFFICER OF HEALTH",)),
    ("Chief financial officer / treasurer", ("CFO", "TREASURER")),
    ("Clerk", ("CITY CLERK", "TOWN CLERK", "REGIONAL CLERK")),
    ("Mayor", ("MAYOR",)),
]
PAY_GROWTH_YEARS = 10

_SLUGS = {slug: (name, region, cds, pop) for slug, name, region, cds, pop in AREAS}


def _placeholders(values) -> str:
    return ", ".join("?" for _ in values)


def _rank(rows: list[dict], key, mine: dict) -> int:
    return sorted(rows, key=key, reverse=True).index(mine) + 1


@cache
def _ontario_municipal_median() -> float:
    return query("""
        SELECT MEDIAN(salary_paid) AS m FROM top_earners_history
        WHERE year = (SELECT MAX(year) FROM top_earners_history) AND sector_id = ?
    """, [MUNICIPAL_SECTOR]).iloc[0, 0]


def area_summary(slug: str) -> dict | None:
    if slug not in _SLUGS:
        return None
    rows = metro_overview()
    a = next(r for r in rows if r["slug"] == slug)
    return a | {
        "areas": len(rows),
        "population_rank": _rank(rows, lambda r: r["population"], a),
        "per_10k_rank": _rank(rows, lambda r: r["per_10k"], a),
        "median_rank": _rank(rows, lambda r: r["median_salary"], a),
        "payroll_per_resident": a["payroll"] / a["population"],
        "ontario_median": _ontario_municipal_median(),
    }


@cache
def area_employers(slug: str) -> list[dict]:
    cds = list(_SLUGS[slug][2])
    return records(query(f"""
        WITH y AS (SELECT MAX(year) AS y FROM top_earners_history),
        e AS (SELECT * FROM employer_wide WHERE sector_id = ? AND geographic_area IN ({_placeholders(cds)})
              AND current_year = (SELECT y FROM y))
        SELECT e.employer_id, e.employer_name, e.municipality, e.current_headcount AS headcount,
               e.current_avg_total_comp AS avg_total_comp, MEDIAN(t.salary_paid) AS median_salary,
               MAX(t.salary_paid) AS max_salary
        FROM e JOIN top_earners_history t ON t.employer_id = e.employer_id AND t.year = (SELECT y FROM y)
        GROUP BY ALL ORDER BY headcount DESC
    """, [MUNICIPAL_SECTOR] + cds))


@cache
def _benchmarks_all() -> list[dict]:
    titles = [t for t, _ in BENCHMARK_ROLES]
    return records(query(f"""
        WITH a(slug, geographic_area) AS (VALUES {_AREA_VALUES}),
        t AS (SELECT t.title_norm, t.salary_paid, w.geographic_area FROM top_earners_history t
              JOIN employer_wide w USING (employer_id)
              WHERE t.year = (SELECT MAX(year) FROM top_earners_history) AND t.sector_id = ?
                AND t.title_norm IN ({_placeholders(titles)})),
        ont AS (SELECT title_norm, MEDIAN(salary_paid) AS ontario_median FROM t GROUP BY 1)
        SELECT a.slug, t.title_norm, COUNT(*)::INTEGER AS n, MEDIAN(t.salary_paid) AS median,
               ANY_VALUE(ont.ontario_median) AS ontario_median
        FROM t JOIN a USING (geographic_area) JOIN ont USING (title_norm) GROUP BY ALL
    """, [MUNICIPAL_SECTOR] + titles))


def area_benchmarks(slug: str) -> list[dict]:
    """Each benchmark job: the area's median vs the same job's Ontario municipal
    median, and its rank among metro areas with MIN_BENCHMARK_N+ people."""
    rows = _benchmarks_all()
    pop = _SLUGS[slug][3]
    out = []
    for title, per_10k in BENCHMARK_ROLES:
        job = [r for r in rows if r["title_norm"] == title]
        peers = [r for r in job if r["n"] >= MIN_BENCHMARK_N]
        mine = next((r for r in job if r["slug"] == slug), None)
        row = {"title_norm": title, "n": mine["n"] if mine else 0, "enough": mine in peers,
               "ontario_median": job[0]["ontario_median"] if job else None, "of": len(peers),
               "per_10k": None, "per_10k_rank": None}
        if row["enough"]:
            row |= {"median": mine["median"], "gap": mine["median"] / mine["ontario_median"] - 1,
                    "rank": _rank(peers, lambda r: r["median"], mine)}
        if per_10k and mine:
            row |= {"per_10k": mine["n"] / pop * 10_000,
                    "per_10k_rank": _rank(job, lambda r: r["n"] / _SLUGS[r["slug"]][3], mine), "per_10k_of": len(job)}
        out.append(row)
    return out


@cache
def _pay_growth_all() -> list[dict]:
    """Average same-person raise by year: people in the same job (Title_Norm,
    or the job title when it isn't normalized) at the same employer in two
    consecutive years. Per area, and for every Ontario municipal employer."""
    return records(query(f"""
        WITH a(slug, geographic_area) AS (VALUES {_AREA_VALUES}),
        h AS (SELECT h.employee_id, h.year, h.employer_id, COALESCE(h.title_norm, h.job_title) AS pos,
                     h.salary_paid, w.geographic_area
              FROM employee_history h JOIN employer_wide w USING (employer_id) WHERE h.sector_id = ?),
        r AS (SELECT c.year, c.geographic_area, c.salary_paid / p.salary_paid - 1 AS raise
              FROM h c JOIN h p ON p.employee_id = c.employee_id AND p.year = c.year - 1
                              AND p.employer_id = c.employer_id AND p.pos = c.pos
              WHERE c.year > (SELECT MAX(year) FROM h) - ?)
        SELECT a.slug, r.year, AVG(r.raise) AS avg_raise, COUNT(*)::INTEGER AS n
        FROM r JOIN a USING (geographic_area) GROUP BY ALL
        UNION ALL
        SELECT 'ontario', year, AVG(raise), COUNT(*)::INTEGER FROM r GROUP BY ALL
    """, [MUNICIPAL_SECTOR, PAY_GROWTH_YEARS]))


def area_pay_growth(slug: str) -> dict:
    rows = _pay_growth_all()
    ont = {r["year"]: r["avg_raise"] for r in rows if r["slug"] == "ontario"}
    series = sorted(
        ({"year": r["year"], "area": r["avg_raise"], "ontario": ont[r["year"]], "n": r["n"]} for r in rows if r["slug"] == slug),
        key=lambda s: s["year"],
    )

    def compound(key):
        total = 1.0
        for s in series:
            total *= 1 + s[key]
        return total - 1

    return {"series": series, "area_total": compound("area"), "ontario_total": compound("ontario")}


@cache
def area_leadership(slug: str) -> list[dict]:
    cds = list(_SLUGS[slug][2])
    titles = [t for _, ts in LEADERSHIP_ROLES for t in ts]
    rows = records(query(f"""
        SELECT t.employee_id, t.first_name, t.last_name, t.title_norm, t.job_title, t.employer_id, t.employer_name,
               t.salary_paid, t.total_comp
        FROM top_earners_history t JOIN employer_wide w USING (employer_id)
        WHERE t.year = (SELECT MAX(year) FROM top_earners_history) AND t.sector_id = ?
          AND w.geographic_area IN ({_placeholders(cds)}) AND t.title_norm IN ({_placeholders(titles)})
        ORDER BY t.salary_paid DESC
    """, [MUNICIPAL_SECTOR] + cds + titles))
    # One per role per employer: the top-paid incumbent. A role's Title_Norm
    # can also hold deputies or district chiefs at some employers.
    groups = []
    for label, ts in LEADERSHIP_ROLES:
        seen, people = set(), []
        for r in rows:
            if r["title_norm"] in ts and r["employer_id"] not in seen:
                seen.add(r["employer_id"])
                people.append(r)
        if people:
            groups.append({"label": label, "people": people})
    return groups


if __name__ == "__main__":
    for a in metro_overview():
        print(a["name"], a["employers"], a["headcount"], round(a["per_10k"], 1), round(a["median_salary"]),
              a["largest_name"], a["trend"][0], a["trend"][-1])
    s = area_summary("peel")
    print(s["population_rank"], s["per_10k_rank"], s["median_rank"], round(s["ontario_median"]))
    print([(e["employer_name"], e["headcount"]) for e in area_employers("peel")])
    for b in area_benchmarks("peel"):
        print(b["title_norm"], b["n"], b.get("median"), b.get("gap"), b.get("rank"), b["of"], b["per_10k"], b["per_10k_rank"])
    g = area_pay_growth("peel")
    print(round(g["area_total"], 3), round(g["ontario_total"], 3), g["series"][-1])
    for grp in area_leadership("peel"):
        print(grp["label"], [(p["employer_name"], round(p["salary_paid"])) for p in grp["people"]])
