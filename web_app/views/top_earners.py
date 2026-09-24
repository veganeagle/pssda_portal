from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.position_profile import list_positions
from access.top_earners import search_top_earners

bp = Blueprint("top_earners", __name__)


@bp.route("/top-earners")
def index():
    sector = request.args.get("sector") or None
    employer = request.args.get("employer") or None
    position = request.args.get("position") or None  # "sector_id::title_norm"

    position_sector_id, title_norm = None, None
    if position and "::" in position:
        position_sector_id, title_norm = position.split("::", 1)

    results = search_top_earners(
        sector_id=position_sector_id or sector,
        employer_contains=employer,
        title_norm=title_norm,
    )
    return render_template(
        "top_earners.html", results=results, sectors=list_sectors(), positions=list_positions()
    )
