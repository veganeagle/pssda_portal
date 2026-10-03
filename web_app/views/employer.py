from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.employer_profile import get_employer_profile, search_employers, sector_employer_counts

bp = Blueprint("employer", __name__)

# Same cycle as charts.js's DONUT_COLORS, so a sector reads the same color
# wherever it shows up across the site.
BAR_COLORS = [
    "#2f6f6b", "#b8831e", "#6b8f3f", "#8b5fb8", "#c2574a",
    "#3f7fb8", "#9a8f3f", "#5f8f8f", "#b85f8f", "#7a7a7a", "#4f6f9f",
]


@bp.route("/employers")
def search():
    name = request.args.get("name") or None
    sector = request.args.get("sector") or None
    show_all = request.args.get("all") == "1"
    results = search_employers(name_contains=name, sector_id=sector, limit=None if show_all else 50)

    sector_counts = sector_employer_counts()
    max_count = max((s["employer_count"] for s in sector_counts), default=0)
    for i, s in enumerate(sector_counts):
        s["color"] = BAR_COLORS[i % len(BAR_COLORS)]
        s["pct_of_max"] = round(s["employer_count"] / max_count * 100, 1) if max_count else 0

    top_employers = search_employers(limit=6)

    return render_template(
        "employers_search.html", results=results, sectors=list_sectors(), show_all=show_all,
        sector_counts=sector_counts, top_employers=top_employers, name=name, sector=sector,
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
    return render_template("employer.html", employer=employer, trend_json=trend_json)
