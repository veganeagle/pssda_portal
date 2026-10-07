"""One sector's own dashboard — same shape as the home dashboard (access.
home_dashboard), scoped down to a single sector_id. Pulled entirely from
existing cubes (employer_wide/_history, position_wide, top_earners_history) —
no new pipeline cube needed.
"""
from __future__ import annotations

from functools import lru_cache

from access._rows import records
from access.db import query
from models.home_dashboard import FastMover, TopEmployer, TopPosition, TrendYear
from models.sector_profile import PositionShare, SectorProfile, SectorTopPosition

# Below this, a role's matched-cohort raise is too easily swung by a handful
# of people. Smaller than the home dashboard's 3,000 floor since we're now
# looking at one sector's own population, not the whole province.
FAST_MOVER_MIN_HEADCOUNT = 50
POSITION_MIX_TOP_N = 5
TOP_POSITION_MIN_HEADCOUNT = 5
TOP_ROLES_LIMIT = 15


@lru_cache(maxsize=1)  # read on every page for the header's Sectors menu
def list_sectors_for_picker() -> list[dict]:
    df = query("SELECT sector_id, sector_name FROM sectors WHERE sector_id NOT IN ('-1', '99') ORDER BY sector_name")
    return records(df)


# Memoized per process: cube data only changes on a refresh, which restarts the app.
@lru_cache(maxsize=64)
def get_sector_profile(sector_id: str) -> SectorProfile | None:
    name_df = query("SELECT sector_name FROM sectors WHERE sector_id = ?", [sector_id])
    if name_df.empty:
        return None
    sector_name = name_df.iloc[0]["sector_name"]

    trend_df = query("""
        SELECT h.year, SUM(h.headcount) AS headcount, SUM(h.total_payroll) AS total_payroll
        FROM employer_history h JOIN employer_wide w ON w.employer_id = h.employer_id
        WHERE w.sector_id = ?
        GROUP BY h.year ORDER BY h.year
    """, [sector_id])
    if trend_df.empty:
        return None
    trend = [TrendYear(**row) for row in records(trend_df)]
    current_year = trend[-1].year
    current_headcount = trend[-1].headcount
    yoy_payroll_change = None
    if len(trend) >= 2 and trend[-2].total_payroll:
        yoy_payroll_change = (trend[-1].total_payroll - trend[-2].total_payroll) / trend[-2].total_payroll

    current_employers = int(query("SELECT COUNT(*) AS n FROM employer_wide WHERE sector_id = ?", [sector_id]).iloc[0]["n"])

    common_df = query("""
        SELECT title_norm, current_headcount AS headcount FROM position_wide WHERE sector_id = ?
        ORDER BY current_headcount DESC LIMIT ?
    """, [sector_id, POSITION_MIX_TOP_N])
    common_positions = list(common_df["title_norm"])
    position_mix = [PositionShare(**row) for row in records(common_df)]
    other_headcount = current_headcount - int(common_df["headcount"].sum())
    if other_headcount > 0:
        position_mix.append(PositionShare(title_norm="Other", headcount=other_headcount))

    movers_df = query("""
        SELECT sector_id, sector_name, title_norm, current_headcount AS headcount, current_avg_raise_matched AS avg_raise_matched
        FROM position_wide
        WHERE sector_id = ? AND current_headcount >= ? AND current_avg_raise_matched IS NOT NULL
        ORDER BY avg_raise_matched DESC LIMIT 6
    """, [sector_id, FAST_MOVER_MIN_HEADCOUNT])
    fastest_movers = [FastMover(**row) for row in records(movers_df)]

    employers_df = query("""
        SELECT employer_id, employer_name, sector_name,
               current_headcount AS headcount, current_total_payroll AS total_payroll
        FROM employer_wide WHERE sector_id = ? ORDER BY current_headcount DESC LIMIT 8
    """, [sector_id])
    top_employers = [TopEmployer(**row) for row in records(employers_df)]

    # Restricted to current_year = this sector's own current year: position_wide's
    # "current" year is per-position (the last year *that role* had data), so a
    # role that quietly stopped being reported (e.g. renamed, or genuinely
    # discontinued) can still rank high on salary while being stale. Picking
    # those into the top 6 only to find zero matching top_earners_history rows
    # for the real current year silently dropped cards — this is why some
    # sectors were coming up short of 6.
    positions_df = query("""
        WITH top6 AS (
            SELECT title_norm, current_headcount AS headcount, current_median_salary AS median_salary
            FROM position_wide
            WHERE sector_id = ? AND title_norm IS NOT NULL AND current_year = ? AND current_headcount >= ?
            ORDER BY current_median_salary DESC LIMIT 6
        ), ranked AS (
            SELECT t.title_norm, t.headcount, t.median_salary,
                   e.employee_id, e.first_name, e.last_name, e.employer_id, e.employer_name,
                   e.salary_paid, e.yoy_salary_increase, e.comparable_to_prior_year,
                   ROW_NUMBER() OVER (PARTITION BY t.title_norm ORDER BY e.total_comp DESC) AS rn
            FROM top6 t
            JOIN top_earners_history e ON e.sector_id = ? AND e.title_norm = t.title_norm AND e.year = ?
        )
        SELECT title_norm, headcount, median_salary, employee_id, first_name, last_name,
               employer_id, employer_name, salary_paid, yoy_salary_increase, comparable_to_prior_year
        FROM ranked WHERE rn = 1 ORDER BY median_salary DESC
    """, [sector_id, current_year, TOP_POSITION_MIN_HEADCOUNT, sector_id, current_year])
    top_positions = [SectorTopPosition(**row) for row in records(positions_df)]

    roles_df = query("""
        SELECT sector_id, sector_name, title_norm,
               current_headcount AS headcount, current_median_salary AS median_salary,
               current_avg_raise_matched AS avg_raise_matched
        FROM position_wide WHERE sector_id = ? AND title_norm IS NOT NULL AND current_year = ?
        ORDER BY current_headcount DESC LIMIT ?
    """, [sector_id, current_year, TOP_ROLES_LIMIT])
    top_roles = [TopPosition(**row) for row in records(roles_df)]

    return SectorProfile(
        sector_id=sector_id, sector_name=sector_name, current_year=current_year,
        current_headcount=current_headcount, current_employers=current_employers,
        current_payroll=trend[-1].total_payroll, yoy_payroll_change=yoy_payroll_change,
        common_positions=common_positions, trend=trend, fastest_movers=fastest_movers,
        position_mix=position_mix, top_employers=top_employers, top_positions=top_positions,
        top_roles=top_roles,
    )


if __name__ == "__main__":
    for sid in ["6", "3", "8"]:
        p = get_sector_profile(sid)
        print(f"{sid}: {p.sector_name} — {p.current_headcount:,} people, {p.current_employers:,} employers, "
              f"${p.current_payroll/1e9:.2f}B, YoY {p.yoy_payroll_change:+.1%}")
        print(f"  fastest movers: {len(p.fastest_movers)}, position mix: {len(p.position_mix)}, "
              f"top employers: {len(p.top_employers)}, top positions: {len(p.top_positions)}")
        for m in p.position_mix:
            print(f"    {m.title_norm}: {m.headcount:,}")
    print("OK")
