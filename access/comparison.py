"""Side-by-side comparison: two employers in the same sector, or the same
normalized position at two different employers in the same sector. Both
sides are always pinned to the dataset's actual current year (never a
possibly-stale per-entity "current year" — see the sector top-positions fix
for why that distinction matters). Cross-sector comparison is deliberately
not offered yet, for either mode — keeps "comparable" well defined without
a design conversation about what cross-sector comparability would even mean.
"""
from __future__ import annotations

from access._rows import records
from access.db import query
from models.comparison import (
    ComparisonSide, ComparisonTrendYear, EarnerComparisonRow, EarnerStats,
    EmployerComparison, PositionComparison, RoleComparisonRow, RoleStats,
)

TOP_ROLES_LIMIT = 8
TOP_EARNERS_LIMIT = 5
TREND_YEARS = 5


def _current_year() -> int:
    return int(query("SELECT MAX(current_year) AS y FROM employer_wide").iloc[0]["y"])


def list_comparable_employers(sector_id: str, exclude_employer_id: str) -> list[dict]:
    """Other employers in the same sector, currently active (so every
    comparison is guaranteed to resolve — no picking a defunct employer and
    hitting an empty comparison)."""
    df = query("""
        SELECT employer_id, employer_name FROM employer_wide
        WHERE sector_id = ? AND employer_id != ? AND current_year = (SELECT MAX(current_year) FROM employer_wide)
        ORDER BY employer_name
    """, [sector_id, exclude_employer_id])
    return records(df)


def list_comparable_employers_for_position(sector_id: str, title_norm: str, exclude_employer_id: str) -> list[dict]:
    """Other employers in the same sector that currently (not just
    historically) offer this exact normalized position."""
    df = query("""
        SELECT employer_id, employer_name FROM employer_position_wide
        WHERE sector_id = ? AND title_norm = ? AND employer_id != ?
          AND current_year = (SELECT MAX(current_year) FROM employer_wide)
        ORDER BY employer_name
    """, [sector_id, title_norm, exclude_employer_id])
    return records(df)


def _employer_side(employer_id: str, current_year: int) -> ComparisonSide:
    meta = records(query(
        "SELECT employer_name, sector_id, sector_name FROM employer_wide WHERE employer_id = ?", [employer_id]
    ))[0]

    hist_rows = records(query("""
        SELECT year, headcount, avg_salary, avg_total_comp, total_payroll
        FROM employer_history WHERE employer_id = ? AND year BETWEEN ? AND ? ORDER BY year
    """, [employer_id, current_year - (TREND_YEARS - 1), current_year]))
    hist_by_year = {r["year"]: r for r in hist_rows}
    cur = hist_by_year[current_year]
    prior = hist_by_year.get(current_year - 1)

    n_new = int(query(
        "SELECT COUNT(*) AS n FROM employee_wide WHERE current_employer_id = ? AND last_seen_year = ? AND first_seen_year = ?",
        [employer_id, current_year, current_year],
    ).iloc[0]["n"])

    n_attrition = int(query("""
        WITH prior_people AS (SELECT DISTINCT employee_id FROM employee_history WHERE employer_id = ? AND year = ?),
        cur_people AS (SELECT DISTINCT employee_id FROM employee_history WHERE employer_id = ? AND year = ?)
        SELECT COUNT(*) AS n FROM prior_people p LEFT JOIN cur_people c USING (employee_id) WHERE c.employee_id IS NULL
    """, [employer_id, current_year - 1, employer_id, current_year]).iloc[0]["n"])

    pct_growth = (cur["headcount"] - prior["headcount"]) / prior["headcount"] if prior and prior["headcount"] else None
    pct_comp_change = (
        (cur["avg_total_comp"] - prior["avg_total_comp"]) / prior["avg_total_comp"]
        if prior and prior["avg_total_comp"] else None
    )
    pct_benefits = (cur["avg_total_comp"] - cur["avg_salary"]) / cur["avg_total_comp"] if cur["avg_total_comp"] else None

    return ComparisonSide(
        employer_id=employer_id, employer_name=meta["employer_name"],
        sector_id=meta["sector_id"], sector_name=meta["sector_name"], current_year=current_year,
        headcount=cur["headcount"], prior_headcount=prior["headcount"] if prior else None,
        pct_headcount_growth=pct_growth, n_new=n_new, n_attrition=n_attrition,
        avg_salary=cur["avg_salary"], avg_total_comp=cur["avg_total_comp"],
        pct_benefits=pct_benefits, disclosed_payroll=cur["total_payroll"],
        pct_comp_change=pct_comp_change, is_matched_raise=False,
        trend=[ComparisonTrendYear(year=r["year"], headcount=r["headcount"]) for r in hist_rows],
    )


def _combo_side(employer_id: str, sector_id: str, title_norm: str, current_year: int) -> ComparisonSide:
    meta = records(query("SELECT employer_name, sector_name FROM employer_wide WHERE employer_id = ?", [employer_id]))[0]

    hist_rows = records(query("""
        SELECT year, headcount, avg_salary, avg_total_comp, avg_raise_matched
        FROM employer_position_history
        WHERE employer_id = ? AND sector_id = ? AND title_norm = ? AND year BETWEEN ? AND ?
        ORDER BY year
    """, [employer_id, sector_id, title_norm, current_year - (TREND_YEARS - 1), current_year]))
    hist_by_year = {r["year"]: r for r in hist_rows}
    cur = hist_by_year[current_year]
    prior = hist_by_year.get(current_year - 1)

    cur_ids = set(query(
        "SELECT DISTINCT employee_id FROM employee_history WHERE employer_id = ? AND sector_id = ? AND title_norm = ? AND year = ?",
        [employer_id, sector_id, title_norm, current_year],
    )["employee_id"])
    prior_ids = set(query(
        "SELECT DISTINCT employee_id FROM employee_history WHERE employer_id = ? AND sector_id = ? AND title_norm = ? AND year = ?",
        [employer_id, sector_id, title_norm, current_year - 1],
    )["employee_id"])
    n_new = len(cur_ids - prior_ids)
    n_attrition = len(prior_ids - cur_ids)

    pct_growth = (cur["headcount"] - prior["headcount"]) / prior["headcount"] if prior and prior["headcount"] else None
    pct_benefits = (cur["avg_total_comp"] - cur["avg_salary"]) / cur["avg_total_comp"] if cur["avg_total_comp"] else None
    # No exact total-payroll figure exists at this granularity (employer x
    # position) in any cube — derived, same scale as the real thing, not a
    # precise sum, but this is purely a "how big is this" context figure.
    disclosed_payroll = cur["avg_salary"] * cur["headcount"]

    return ComparisonSide(
        employer_id=employer_id, employer_name=meta["employer_name"],
        sector_id=sector_id, sector_name=meta["sector_name"], current_year=current_year,
        headcount=cur["headcount"], prior_headcount=prior["headcount"] if prior else None,
        pct_headcount_growth=pct_growth, n_new=n_new, n_attrition=n_attrition,
        avg_salary=cur["avg_salary"], avg_total_comp=cur["avg_total_comp"],
        pct_benefits=pct_benefits, disclosed_payroll=disclosed_payroll,
        pct_comp_change=cur["avg_raise_matched"], is_matched_raise=True,
        trend=[ComparisonTrendYear(year=r["year"], headcount=r["headcount"]) for r in hist_rows],
    )


def _roles_comparison(employer_id_a: str, employer_id_b: str, current_year: int) -> list[RoleComparisonRow]:
    a_roles = records(query("""
        SELECT title_norm, headcount, median_salary, avg_raise_matched
        FROM employer_top_positions WHERE employer_id = ? AND year = ? ORDER BY rank LIMIT ?
    """, [employer_id_a, current_year, TOP_ROLES_LIMIT]))

    b_lookup = {
        r["title_norm"]: r for r in records(query("""
            SELECT title_norm, current_headcount AS headcount, current_median_salary AS median_salary,
                   current_avg_raise_matched AS avg_raise_matched
            FROM employer_position_wide WHERE employer_id = ? AND current_year = ?
        """, [employer_id_b, current_year]))
    }

    rows = []
    for r in a_roles:
        b = b_lookup.get(r["title_norm"])
        rows.append(RoleComparisonRow(
            title_norm=r["title_norm"],
            a=RoleStats(headcount=r["headcount"], median_salary=r["median_salary"], avg_raise_matched=r["avg_raise_matched"]),
            b=RoleStats(headcount=b["headcount"], median_salary=b["median_salary"], avg_raise_matched=b["avg_raise_matched"]) if b else None,
        ))
    return rows


def _top_earners(
    employer_id: str, current_year: int, sector_id: str | None = None, title_norm: str | None = None,
) -> list[dict]:
    conditions = ["employer_id = ?", "year = ?"]
    params: list = [employer_id, current_year]
    if sector_id and title_norm:
        conditions += ["sector_id = ?", "title_norm = ?"]
        params += [sector_id, title_norm]
    return records(query(f"""
        SELECT employee_id, first_name, last_name, job_title, title_norm, total_comp
        FROM top_earners_history WHERE {' AND '.join(conditions)}
        ORDER BY total_comp DESC LIMIT ?
    """, params + [TOP_EARNERS_LIMIT]))


def _match_earners(a_earners: list[dict], b_earners: list[dict]) -> list[EarnerComparisonRow]:
    """Walk A's top earners in rank order; pair each with the best unmatched
    B entry sharing the same normalized title (combo mode: every entry
    already shares the same title, so this just pairs by rank). No title ->
    never matched, always its own row. Leftover unmatched B entries get
    their own rows after. Between len(a) (full match) and len(a)+len(b)
    rows (no overlap at all).
    """
    rows = []
    b_pool = list(b_earners)
    for a in a_earners:
        match = None
        if a.get("title_norm"):
            for i, b in enumerate(b_pool):
                if b.get("title_norm") == a["title_norm"]:
                    match = b_pool.pop(i)
                    break
        rows.append(EarnerComparisonRow(a=EarnerStats(**a), b=EarnerStats(**match) if match else None))
    for b in b_pool:
        rows.append(EarnerComparisonRow(a=None, b=EarnerStats(**b)))
    return rows


def compare_employers(employer_id_a: str, employer_id_b: str) -> EmployerComparison:
    current_year = _current_year()
    a = _employer_side(employer_id_a, current_year)
    b = _employer_side(employer_id_b, current_year)
    roles = _roles_comparison(employer_id_a, employer_id_b, current_year)
    earners = _match_earners(
        _top_earners(employer_id_a, current_year), _top_earners(employer_id_b, current_year),
    )
    return EmployerComparison(a=a, b=b, roles=roles, earners=earners)


def compare_positions(sector_id: str, title_norm: str, employer_id_a: str, employer_id_b: str) -> PositionComparison:
    current_year = _current_year()
    a = _combo_side(employer_id_a, sector_id, title_norm, current_year)
    b = _combo_side(employer_id_b, sector_id, title_norm, current_year)
    earners = _match_earners(
        _top_earners(employer_id_a, current_year, sector_id, title_norm),
        _top_earners(employer_id_b, current_year, sector_id, title_norm),
    )
    return PositionComparison(title_norm=title_norm, a=a, b=b, earners=earners)


if __name__ == "__main__":
    comp = compare_employers("10_0013", "10_0018")  # TDSB vs Peel DSB
    print(f"employers: {comp.a.employer_name} ({comp.a.headcount:,}) vs {comp.b.employer_name} ({comp.b.headcount:,})")
    print(f"  roles compared: {len(comp.roles)}, earners rows: {len(comp.earners)}")
    matched_roles = sum(1 for r in comp.roles if r.b is not None)
    print(f"  roles with a match on both sides: {matched_roles}/{len(comp.roles)}")
    matched_earners = sum(1 for r in comp.earners if r.a is not None and r.b is not None)
    print(f"  earner rows with both sides filled: {matched_earners}/{len(comp.earners)}")

    pcomp = compare_positions("10", "TEACHER", "10_0013", "10_0018")
    print(f"positions: TEACHER at {pcomp.a.employer_name} ({pcomp.a.headcount:,}) vs {pcomp.b.employer_name} ({pcomp.b.headcount:,})")
    print(f"  raise: {pcomp.a.pct_comp_change}, {pcomp.b.pct_comp_change} (matched={pcomp.a.is_matched_raise})")

    print(f"comparable employers for TDSB's sector: {len(list_comparable_employers('10', '10_0013'))}")
    print(f"comparable employers for TDSB's TEACHER role: {len(list_comparable_employers_for_position('10', 'TEACHER', '10_0013'))}")
