from flask import Blueprint, render_template, request

from access.employee_profile import get_employee_profile
from access.employee_search import list_sectors, search_employees

bp = Blueprint("profile", __name__)


@bp.route("/")
@bp.route("/search")
def search():
    args = request.args
    filters = {
        "first": args.get("first") or None,
        "last": args.get("last") or None,
        "middle": args.get("middle") or None,
        "sector": args.get("sector") or None,
        "employer_contains": args.get("employer") or None,
        "title_contains": args.get("title") or None,
        "year": int(args["year"]) if args.get("year") else None,
    }
    searched = any(filters.values())
    outcome = search_employees(**filters) if searched else None
    return render_template("search.html", searched=searched, outcome=outcome, sectors=list_sectors())


@bp.route("/profile/<employee_id>")
def profile_page(employee_id):
    profile = get_employee_profile(employee_id)
    if profile is None:
        return render_template("not_found.html", employee_id=employee_id), 404
    return render_template("profile.html", profile=profile)
