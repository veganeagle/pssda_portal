from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.position_profile import list_positions
from access.top_earners import list_available_years, search_top_earners

bp = Blueprint("top_earners", __name__)


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

    return render_template(
        "top_earners.html", results=results, sectors=list_sectors(), positions=list_positions(),
        year=year, prev_year=prev_year, next_year=next_year,
    )
