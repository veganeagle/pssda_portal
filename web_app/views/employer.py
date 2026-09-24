from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.employer_profile import get_employer_profile, search_employers

bp = Blueprint("employer", __name__)


@bp.route("/employers")
def search():
    name = request.args.get("name") or None
    sector = request.args.get("sector") or None
    results = search_employers(name_contains=name, sector_id=sector)
    return render_template("employers_search.html", results=results, sectors=list_sectors())


@bp.route("/employer/<employer_id>")
def profile_page(employer_id):
    employer = get_employer_profile(employer_id)
    if employer is None:
        return render_template("not_found.html", what="employer", key=employer_id), 404
    return render_template("employer.html", employer=employer)
