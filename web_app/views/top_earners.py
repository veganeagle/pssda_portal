from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.position_profile import list_positions
from access.top_earners import (
    TOP_N_PROVINCE, list_available_years, search_top_earners, sector_top_earners_overview,
)

bp = Blueprint("top_earners", __name__)

# Same cycle as charts.js's DONUT_COLORS, so a sector's dot here reads as
# the same family of color used in donut charts elsewhere on the site.
SECTOR_COLORS = [
    "#2f6f6b", "#b8831e", "#6b8f3f", "#8b5fb8", "#c2574a",
    "#3f7fb8", "#9a8f3f", "#5f8f8f", "#b85f8f", "#7a7a7a", "#4f6f9f",
]


@bp.route("/top-earners")
def index():
    sector = request.args.get("sector") or None
    employer = request.args.get("employer") or None
    position = request.args.get("position") or None  # "sector_id::title_norm"

    position_sector_id, title_norm = None, None
    if position and "::" in position:
        position_sector_id, title_norm = position.split("::", 1)

    years = list_available_years()
    year = request.args.get("year", type=int)
    if year not in years:
        year = years[0] if years else None

    results = search_top_earners(
        sector_id=position_sector_id or sector,
        employer_contains=employer,
        title_norm=title_norm,
        year=year,
    )
    idx = years.index(year) if year in years else -1
    prev_year = years[idx + 1] if 0 <= idx < len(years) - 1 else None  # older
    next_year = years[idx - 1] if idx > 0 else None  # more recent

    sector_overview = sector_top_earners_overview()
    max_employees = max((s["n_employees"] for s in sector_overview), default=0)
    for i, s in enumerate(sector_overview):
        s["pct_of_max"] = round(s["n_employees"] / max_employees * 100, 1) if max_employees else 0
        s["pct_top_province"] = round(s["n_in_top_province"] / TOP_N_PROVINCE * 100, 1)
        s["color"] = SECTOR_COLORS[i % len(SECTOR_COLORS)]

    return render_template(
        "top_earners.html", results=results, sectors=list_sectors(), positions=list_positions(),
        year=year, prev_year=prev_year, next_year=next_year, sector_overview=sector_overview,
        top_n_province=TOP_N_PROVINCE,
    )
