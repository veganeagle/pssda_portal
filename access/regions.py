"""One position (sector_id + title_norm — the comparable unit) across Ontario's
four regions, for the position page's regional chart. Region is the
employer's (employer_wide); people at province-wide employers (ministries,
OPG, ...) have none and only count toward the Ontario-wide figures.
"""
from __future__ import annotations

from functools import cache, lru_cache

from access._rows import records
from access.db import query

REGIONS = ["NORTH", "EAST", "CENTRAL", "WEST"]  # fixed display order, north to south-west
MIN_REGION_COUNT = 10  # below this a region's percentiles are one or two people's pay


@lru_cache(maxsize=256)
def position_by_region(sector_id: str, title_norm: str, year: int) -> dict:
    """P10 / median / P90 salary paid in each region and Ontario-wide
    (everyone in the position, located or not)."""
    df = query("""
        WITH base AS (
            SELECT t.salary_paid, e.region
            FROM top_earners_history t LEFT JOIN employer_wide e USING (employer_id)
            WHERE t.year = ? AND t.sector_id = ? AND t.title_norm = ?
        )
        SELECT CASE WHEN GROUPING(region) = 1 THEN 'ONTARIO' ELSE region END AS region,
               COUNT(*)::INTEGER AS n,
               QUANTILE_CONT(salary_paid, 0.1) AS p10,
               MEDIAN(salary_paid) AS median,
               QUANTILE_CONT(salary_paid, 0.9) AS p90
        FROM base
        GROUP BY GROUPING SETS ((region), ())
    """, [year, sector_id, title_norm])
    rows = {r["region"]: r for r in records(df)}
    regions = [rows.get(r, {"n": 0}) | {"region": r} for r in REGIONS]
    return {
        "ontario": rows["ONTARIO"],
        "regions": regions,
        "n_unlocated": rows["ONTARIO"]["n"] - sum(r["n"] for r in regions),
    }



# ---- Regions tab (prototype): location premiums, regional trends, sector overview ----

PREMIUM_MIN_REGION_N = 25      # people in the region, both years
PREMIUM_MIN_ONTARIO_N = 200    # people in the position province-wide
PREMIUM_MIN = 0.02             # region median at least 2% above Ontario's, in both years
UNIFORM_MAX_SPREAD = 0.03      # all four regions within 3% of each other
PREMIUM_LIMIT = 5
TREND_YEARS = 10
TREND_END_YEARS = 3            # each end of a trend is a 3-year average: a single year is often retroactive pay
TREND_LIMIT = 6
# Pay for these reflects organization size or how doctors are paid (salary vs.
# stipend), not location — a CEO "Central premium" is big hospitals, not Toronto.
EXCLUDED_TITLES = (
    "CEO", "CAO", "CFO", "COO", "CIO", "PRESIDENT", "VICE PRESIDENT", "EXECUTIVE DIRECTOR", "DIRECTOR",
    "GENERAL MANAGER", "COMMISSIONER", "SUPERINTENDENT", "DIRECTOR OF EDUCATION", "DEAN", "ASSOCIATE DEAN",
    "POLICE CHIEF", "DEPUTY POLICE CHIEF", "FIRE CHIEF", "DEPUTY FIRE CHIEF", "CHIEF", "DEPUTY CHIEF", "MAYOR",
    "PHYSICIAN", "PATHOLOGIST", "PSYCHIATRIST", "RADIOLOGIST", "ANESTHESIOLOGIST", "SURGEON",
)

# Region median / Ontario median for every position, region and year. Region
# rows need MIN_REGION_COUNT people; Ontario includes people with no region.
_RATIOS_SQL = f"""
    WITH b AS (
        SELECT t.year, t.sector_id, t.sector_name, t.title_norm, t.salary_paid, e.region
        FROM top_earners_history t LEFT JOIN employer_wide e USING (employer_id)
        WHERE t.title_norm IS NOT NULL
    ), ont AS (
        SELECT year, sector_id, sector_name, title_norm, COUNT(*) AS n_ontario, MEDIAN(salary_paid) AS median_ontario
        FROM b GROUP BY ALL
    ), reg AS (
        SELECT year, sector_id, title_norm, region, COUNT(*) AS n, MEDIAN(salary_paid) AS median
        FROM b WHERE region IN ({", ".join(f"'{r}'" for r in REGIONS)}) GROUP BY ALL
    )
    SELECT r.*, o.sector_name, o.n_ontario, o.median_ontario, r.median / o.median_ontario AS ratio
    FROM reg r JOIN ont o USING (year, sector_id, title_norm)
    WHERE r.n >= {MIN_REGION_COUNT}
      AND r.title_norm NOT IN ({", ".join(f"'{t}'" for t in EXCLUDED_TITLES)})
"""


@cache
def location_premiums() -> dict:
    """Per region, the positions paid most above their own Ontario median, in
    the latest year and the one before (one-year jumps are often retroactive
    pay); plus positions paid the same in every region."""
    df = query(f"""
        WITH r AS ({_RATIOS_SQL}),
        y AS (SELECT MAX(year) AS y FROM r),
        cur AS (SELECT * FROM r WHERE year = (SELECT y FROM y)),
        prev AS (SELECT sector_id, title_norm, region, ratio AS prior_ratio, n AS prior_n
                 FROM r WHERE year = (SELECT y FROM y) - 1)
        SELECT cur.year, cur.sector_id, cur.sector_name, cur.title_norm, cur.region, cur.n, cur.n_ontario,
               cur.median_ontario, cur.ratio, prev.prior_ratio
        FROM cur JOIN prev USING (sector_id, title_norm, region)
        WHERE cur.n >= ? AND prev.prior_n >= ? AND cur.n_ontario >= ?
    """, [PREMIUM_MIN_REGION_N, PREMIUM_MIN_REGION_N, PREMIUM_MIN_ONTARIO_N])
    rows = [r | {"premium": r["ratio"] - 1, "prior_premium": r["prior_ratio"] - 1} for r in records(df)]
    premiums = {
        region: sorted(
            (r for r in rows if r["region"] == region and r["premium"] >= PREMIUM_MIN and r["prior_premium"] >= PREMIUM_MIN),
            key=lambda r: -r["ratio"],
        )[:PREMIUM_LIMIT]
        for region in REGIONS
    }
    by_position: dict[tuple, list] = {}
    for r in rows:
        by_position.setdefault((r["sector_id"], r["title_norm"]), []).append(r)
    uniform = sorted(
        (
            {**rs[0], "spread": max(x["ratio"] for x in rs) - min(x["ratio"] for x in rs)}
            for rs in by_position.values() if len(rs) == len(REGIONS)
        ),
        key=lambda r: -r["n_ontario"],
    )
    uniform = [u for u in uniform if u["spread"] < UNIFORM_MAX_SPREAD]
    return {"year": rows[0]["year"] if rows else None, "premiums": premiums, "uniform": uniform}


@cache
def regional_trends() -> list[dict]:
    """Positions whose region-vs-Ontario ratio moved most over TREND_YEARS —
    first TREND_END_YEARS averaged against the last TREND_END_YEARS, each year
    with PREMIUM_MIN_REGION_N+ people — each with every region's ratio for
    every year in between."""
    df = query(f"""
        WITH r AS ({_RATIOS_SQL}),
        y AS (SELECT MAX(year) AS y FROM r),
        ends AS (
            SELECT sector_id, sector_name, title_norm, region,
                   CASE WHEN year <= (SELECT y FROM y) - ? + ? - 1 THEN 'first' ELSE 'last' END AS period,
                   AVG(ratio) AS ratio, COUNT(*) AS years, MIN(n_ontario) AS n_ontario
            FROM r
            WHERE n >= ? AND (year <= (SELECT y FROM y) - ? + ? - 1 AND year >= (SELECT y FROM y) - ?
                              OR year > (SELECT y FROM y) - ?)
            GROUP BY ALL
        ),
        moves AS (
            SELECT a.sector_id, a.sector_name, a.title_norm, a.region,
                   b.ratio AS first_ratio, a.ratio AS last_ratio, a.ratio - b.ratio AS change
            FROM ends a JOIN ends b USING (sector_id, title_norm, region)
            WHERE a.period = 'last' AND b.period = 'first' AND a.years = ? AND b.years = ? AND a.n_ontario >= ?
            ORDER BY ABS(a.ratio - b.ratio) DESC
            LIMIT ?
        )
        SELECT m.*, r.year, r.region AS series_region, r.ratio
        FROM moves m JOIN r USING (sector_id, title_norm)
        WHERE r.year >= (SELECT y FROM y) - ?
        ORDER BY ABS(m.change) DESC, r.year
    """, [TREND_YEARS, TREND_END_YEARS, PREMIUM_MIN_REGION_N, TREND_YEARS, TREND_END_YEARS, TREND_YEARS,
          TREND_END_YEARS, TREND_END_YEARS, TREND_END_YEARS, PREMIUM_MIN_ONTARIO_N, TREND_LIMIT, TREND_YEARS])
    trends: dict[tuple, dict] = {}
    for row in records(df):
        key = (row["sector_id"], row["title_norm"], row["region"])
        t = trends.setdefault(key, {k: row[k] for k in (
            "sector_id", "sector_name", "title_norm", "region", "first_ratio", "last_ratio", "change")} | {"series": {}})
        t["series"].setdefault(row["series_region"], []).append({"year": row["year"], "ratio": row["ratio"]})
    return list(trends.values())


@cache
def sector_region_overview() -> list[dict]:
    """Latest year, per sector and region: employers, disclosed employees,
    median salary. Region "NONE" is province-wide employers."""
    df = query("""
        SELECT t.year, t.sector_id, t.sector_name, COALESCE(e.region, 'NONE') AS region,
               COUNT(DISTINCT t.employer_id)::INTEGER AS employers, COUNT(*)::INTEGER AS headcount,
               MEDIAN(t.salary_paid) AS median_salary
        FROM top_earners_history t LEFT JOIN employer_wide e USING (employer_id)
        WHERE t.year = (SELECT MAX(year) FROM top_earners_history) AND t.sector_id NOT IN ('-1', '99')
        GROUP BY ALL ORDER BY t.sector_name
    """)
    return records(df)


if __name__ == "__main__":
    lp = location_premiums()
    for reg, rs in lp["premiums"].items():
        print(reg, [(r["title_norm"], round(r["ratio"] - 1, 3)) for r in rs])
    print("uniform", [(u["title_norm"], round(u["spread"], 3)) for u in lp["uniform"]])
    for t in regional_trends():
        print(t["title_norm"], t["region"], round(t["first_ratio"], 3), round(t["last_ratio"], 3), len(t["series"]))
    print(len(sector_region_overview()), "sector-region rows")
    r = position_by_region("8", "CONSTABLE", 2025)
    print(r["ontario"], r["n_unlocated"])
    for x in r["regions"]:
        print(x)
