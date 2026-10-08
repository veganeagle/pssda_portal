from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.employer_profile import list_employers_for_filter
from access.position_profile import get_position_profile, search_positions, sector_position_overview
from access.sector_profile import get_sector_profile
from web_app.formatting import proper_case

bp = Blueprint("position", __name__)

# Same cycle as charts.js's DONUT_COLORS, so a sector's dot here reads as
# the same family of color used in donut charts elsewhere on the site.
SECTOR_COLORS = [
    "#2f6f6b", "#b8831e", "#6b8f3f", "#8b5fb8", "#c2574a",
    "#3f7fb8", "#9a8f3f", "#5f8f8f", "#b85f8f", "#7a7a7a", "#4f6f9f",
]


@bp.route("/positions")
def search():
    title = request.args.get("title") or None
    sector = request.args.get("sector") or None
    employer = request.args.get("emp") or None
    results = search_positions(title_contains=title, sector_id=sector, employer_id=employer)

    sector_overview = sector_position_overview()
    max_headcount = max((s["total_headcount"] for s in sector_overview), default=0)
    for i, s in enumerate(sector_overview):
        s["pct_of_max"] = round(s["total_headcount"] / max_headcount * 100, 1) if max_headcount else 0
        s["pct_mapped"] = round(s["normed_headcount"] / s["total_headcount"] * 100, 1) if s["total_headcount"] else 0
        s["color"] = SECTOR_COLORS[i % len(SECTOR_COLORS)]

    # A selected sector swaps the all-sector overview for a compact view of
    # that sector (fastest movers + position mix), drawn from the sector
    # dashboard's own data.
    sector_view = get_sector_profile(sector) if sector else None
    position_mix_json = [
        {"name": proper_case(m.title_norm), "value": m.headcount, "label": f"{m.headcount:,}"}
        for m in sector_view.position_mix
    ] if sector_view else None

    return render_template(
        "positions_search.html", results=results, sectors=list_sectors(), sector_overview=sector_overview,
        employers_for_filter=list_employers_for_filter(), employer=employer,
        sector_view=sector_view, position_mix_json=position_mix_json,
    )


@bp.route("/position/<sector_id>/<title_norm>")
def profile_page(sector_id, title_norm):
    position = get_position_profile(sector_id, title_norm)
    if position is None:
        return render_template("not_found.html", what="position", key=f"{sector_id}/{title_norm}"), 404
    return render_template("position.html", position=position)
