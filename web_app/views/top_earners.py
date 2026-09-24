from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.top_earners import search_top_earners

bp = Blueprint("top_earners", __name__)


@bp.route("/top-earners")
def index():
    sector = request.args.get("sector") or None
    employer = request.args.get("employer") or None
    position = request.args.get("position") or None

    results = search_top_earners(sector_id=sector, employer_contains=employer, title_contains=position)
    return render_template("top_earners.html", results=results, sectors=list_sectors())
