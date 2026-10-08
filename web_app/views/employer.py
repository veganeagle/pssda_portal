from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.employer_profile import (
    get_employer_profile, list_employers_for_filter, search_employers, sector_employer_growth, sector_employer_mix,
    sector_employer_overview,
)
from web_app.formatting import proper_case
from access.sector_profile import list_sectors_for_picker

bp = Blueprint("employer", __name__)

# Same cycle as charts.js's DONUT_COLORS, so a sector's dot here reads as
# the same family of color used in donut charts elsewhere on the site.
SECTOR_COLORS = [
    "#2f6f6b", "#b8831e", "#6b8f3f", "#8b5fb8", "#c2574a",
    "#3f7fb8", "#9a8f3f", "#5f8f8f", "#b85f8f", "#7a7a7a", "#4f6f9f",
]


@bp.route("/employers")
def search():
    name = request.args.get("name") or None
    sector = request.args.get("sector") or None
    show_all = request.args.get("all") == "1"
    results = search_employers(name_contains=name, sector_id=sector, limit=None if show_all else 50)

    sector_overview = sector_employer_overview()
    max_headcount = max((s["total_headcount"] for s in sector_overview), default=0)
    for i, s in enumerate(sector_overview):
        s["pct_of_max"] = round(s["total_headcount"] / max_headcount * 100, 1) if max_headcount else 0
        s["color"] = SECTOR_COLORS[i % len(SECTOR_COLORS)]

    # A selected sector swaps the all-sector overview for that sector's
    # fastest-growing employers and its share of disclosed employees.
    sector_view = next((s for s in sector_overview if s["sector_id"] == sector), None) if sector else None
    employer_growth = sector_employer_growth(sector) if sector_view else None
    employer_mix_json = [
        {"name": proper_case(m["employer_name"]) if m["employer_id"] else f"All other ({m['n_employers']} employers)",
         "value": m["headcount"], "label": f"{m['headcount']:,}"}
        for m in sector_employer_mix(sector)
    ] if sector_view else None

    return render_template(
        "employers_search.html", results=results, sectors=list_sectors(), show_all=show_all,
        sector_overview=sector_overview, name=name, sector=sector,
        sector_view=sector_view, employer_growth=employer_growth, employer_mix_json=employer_mix_json,
    )


@bp.route("/employer/<employer_id>")
def profile_page(employer_id):
    employer = get_employer_profile(employer_id)
    if employer is None:
        return render_template("not_found.html", what="employer", key=employer_id), 404
    trend_json = [
        {"year": h.year, "headcount": h.headcount, "total_payroll": h.total_payroll}
        for h in sorted(employer.history, key=lambda h: h.year)
    ]
    # All active employers, any sector — the compare box's sector picker lets
    # the right-hand side come from a different sector than this one (e.g.
    # comparing a university to a college).
    all_employers = [e for e in list_employers_for_filter(active_only=True) if e["employer_id"] != employer_id]
    return render_template(
        "employer.html", employer=employer, trend_json=trend_json,
        all_employers=all_employers, sectors=list_sectors_for_picker(),
    )
