from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.position_profile import get_position_profile, search_positions

bp = Blueprint("position", __name__)


@bp.route("/positions")
def search():
    title = request.args.get("title") or None
    sector = request.args.get("sector") or None
    results = search_positions(title_contains=title, sector_id=sector)
    return render_template("positions_search.html", results=results, sectors=list_sectors())


@bp.route("/position/<sector_id>/<title_norm>")
def profile_page(sector_id, title_norm):
    position = get_position_profile(sector_id, title_norm)
    if position is None:
        return render_template("not_found.html", what="position", key=f"{sector_id}/{title_norm}"), 404
    return render_template("position.html", position=position)
