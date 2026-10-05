"""The /search page's dashboard: province-wide trend, sector mix, fastest-rising
roles, largest employers, the top 15 positions by headcount, and a top-earners
preview. Pulled straight from existing cubes (employer_wide/_history,
position_wide, top_earners_history) — no new pipeline cube needed.
"""
from __future__ import annotations

from functools import cache

from access._rows import records
from access.db import query
from models.home_dashboard import (
    FastMover, HomeDashboard, NotableRoleLeader, SectorShare, TopEarnerPreview,
    TopEmployer, TopPosition, TrendYear,
)

# Below this, a role's matched-cohort raise is too easily swung by a handful
# of people — "fastest movers" should read as a real, large-population signal.
FAST_MOVER_MIN_HEADCOUNT = 3000


# Memoized per process: cube data only changes on a refresh, which restarts the app.
@cache
def get_year_range() -> tuple[int, int]:
    """First and latest disclosure year in the published data — for the
    site-wide header label, so it never needs a literal."""
    df = query("SELECT MIN(year) AS first_year, MAX(year) AS last_year FROM employer_history")
    return int(df.first_year[0]), int(df.last_year[0])


@cache
def get_home_dashboard() -> HomeDashboard:
    trend_df = query("""
        SELECT year, SUM(headcount) AS headcount, SUM(total_payroll) AS total_payroll
        FROM employer_history GROUP BY year ORDER BY year
    """)
    trend = [TrendYear(**row) for row in records(trend_df)]
    current_year = trend[-1].year

    sector_df = query("""
        SELECT sector_name, SUM(current_headcount) AS headcount, SUM(current_total_payroll) AS total_payroll
        FROM employer_wide
        WHERE sector_name IS NOT NULL AND sector_name != 'SECONDED'
        GROUP BY sector_name ORDER BY total_payroll DESC
    """)
    sectors = [SectorShare(**row) for row in records(sector_df)]

    movers_df = query("""
        SELECT sector_id, sector_name, title_norm, current_headcount AS headcount, current_avg_raise_matched AS avg_raise_matched
        FROM position_wide
        WHERE current_headcount >= ? AND current_avg_raise_matched IS NOT NULL
        ORDER BY avg_raise_matched DESC LIMIT 6
    """, [FAST_MOVER_MIN_HEADCOUNT])
    fastest_movers = [FastMover(**row) for row in records(movers_df)]

    employers_df = query("""
        SELECT employer_id, employer_name, sector_name,
               current_headcount AS headcount, current_total_payroll AS total_payroll
        FROM employer_wide ORDER BY current_headcount DESC LIMIT 8
    """)
    top_employers = [TopEmployer(**row) for row in records(employers_df)]

    positions_df = query("""
        SELECT sector_id, sector_name, title_norm,
               current_headcount AS headcount, current_median_salary AS median_salary,
               current_avg_raise_matched AS avg_raise_matched
        FROM position_wide ORDER BY current_headcount DESC LIMIT 15
    """)
    top_positions = [TopPosition(**row) for row in records(positions_df)]

    earners_df = query("""
        SELECT employee_id, first_name, last_name, job_title, employer_id, employer_name, total_comp
        FROM top_earners_history
        WHERE year = (SELECT MAX(year) FROM top_earners_history)
        ORDER BY total_comp DESC LIMIT 6
    """)
    top_earners = [TopEarnerPreview(**row) for row in records(earners_df)]

    notable_df = query("""
        SELECT role_label, employee_id, first_name, last_name, employer_id, employer_name, sector_name,
               job_title_raw, salary_paid, pool_size, yoy_salary_increase, comparable_to_prior_year
        FROM notable_roles_current ORDER BY salary_paid DESC
    """)
    notable_roles = [NotableRoleLeader(**row) for row in records(notable_df)]

    return HomeDashboard(
        current_year=current_year,
        current_headcount=trend[-1].headcount,
        current_payroll=trend[-1].total_payroll,
        current_employers=int(query("SELECT COUNT(*) AS n FROM employer_wide").iloc[0]["n"]),
        trend=trend,
        sectors=sectors,
        fastest_movers=fastest_movers,
        top_employers=top_employers,
        top_positions=top_positions,
        top_earners=top_earners,
        notable_roles=notable_roles,
    )


if __name__ == "__main__":
    d = get_home_dashboard()
    print(f"{d.current_year}: {d.current_headcount:,} people, ${d.current_payroll/1e9:.2f}B, {d.current_employers:,} employers")
    print(f"{len(d.trend)} trend years, {len(d.sectors)} sectors, {len(d.fastest_movers)} fast movers, "
          f"{len(d.top_employers)} top employers, {len(d.top_positions)} top positions, "
          f"{len(d.top_earners)} top earners, {len(d.notable_roles)} notable roles")
    assert d.trend[0].year < d.trend[-1].year
    print("OK")
