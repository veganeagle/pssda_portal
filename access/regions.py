"""One position (sector_id + title_norm — the comparable unit) across Ontario's
four regions, for the position page's regional chart. Region is the
employer's (employer_wide); people at province-wide employers (ministries,
OPG, ...) have none and only count toward the Ontario-wide figures.
"""
from __future__ import annotations

from functools import lru_cache

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


if __name__ == "__main__":
    r = position_by_region("8", "CONSTABLE", 2025)
    print(r["ontario"], r["n_unlocated"])
    for x in r["regions"]:
        print(x)
