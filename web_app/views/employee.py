from flask import Blueprint, render_template, request

from access.employee_profile import get_employee_profile
from access.employee_search import list_sectors, search_employees

bp = Blueprint("employee", __name__)


def _parse_year(raw):
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None  # garbage input just means "no year filter", not a crash


@bp.route("/search")
def search():
    args = request.args
    scope_employer_id = args.get("employer_id") or None
    scope_sector_id = args.get("scope_sector_id") or None
    scope_title_norm = args.get("scope_title_norm") or None
    scope_label = args.get("scope_label") or None
    position = (scope_sector_id, scope_title_norm) if scope_sector_id and scope_title_norm else None

    filters = {
        "first": args.get("first") or None,
        "last": args.get("last") or None,
        "middle": args.get("middle") or None,
        "sector": args.get("sector") or None,
        "employer_contains": args.get("employer") or None,
        "title_contains": args.get("title") or None,
        "year": _parse_year(args.get("year")),
        "include_inactive": args.get("status") == "all",
        "employer_id": scope_employer_id,
        "position": position,
    }
    searched = any(v for k, v in filters.items() if k != "include_inactive")
    outcome = search_employees(**filters) if searched else None
    return render_template(
        "search.html", searched=searched, outcome=outcome, sectors=list_sectors(),
        scope_employer_id=scope_employer_id, scope_sector_id=scope_sector_id, scope_title_norm=scope_title_norm,
        scope_label=scope_label,
    )


@bp.route("/employee/<employee_id>")
def profile_page(employee_id):
    profile = get_employee_profile(employee_id)
    if profile is None:
        return render_template("not_found.html", what="employee", key=employee_id), 404
    return render_template("employee.html", profile=profile)
