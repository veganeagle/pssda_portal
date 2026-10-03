from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.employer_profile import get_employer_profile, search_employers, sector_employer_overview

bp = Blueprint("employer", __name__)


@bp.route("/employers")
def search():
    name = request.args.get("name") or None
    sector = request.args.get("sector") or None
    show_all = request.args.get("all") == "1"
    results = search_employers(name_contains=name, sector_id=sector, limit=None if show_all else 50)

    sector_overview = sector_employer_overview()

    return render_template(
        "employers_search.html", results=results, sectors=list_sectors(), show_all=show_all,
        sector_overview=sector_overview, name=name, sector=sector,
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
