from flask import Blueprint, render_template, request

from access.employee_profile import get_employee_profile
from access.employee_search import list_sectors, search_employees, sector_population_overview
from access.employer_position_profile import list_positions_for_employer
from access.employer_profile import list_employers_for_filter

bp = Blueprint("employee", __name__)

# Same cycle as charts.js's DONUT_COLORS, so a sector's dot here reads as
# the same family of color used in donut charts elsewhere on the site.
SECTOR_COLORS = [
    "#2f6f6b", "#b8831e", "#6b8f3f", "#8b5fb8", "#c2574a",
    "#3f7fb8", "#9a8f3f", "#5f8f8f", "#b85f8f", "#7a7a7a", "#4f6f9f",
]


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
    scoped = bool(scope_employer_id or scope_sector_id)  # landed here from the mini search box elsewhere
    scope_position = (scope_sector_id, scope_title_norm) if scope_sector_id and scope_title_norm else None

    # The general page's own sector->employer->position cascade uses its own
    # param names (`emp`, `position`) so picking something there never flips
    # the page into "scoped" mode (which hides these very fields) the way
    # landing here from the mini search box's employer_id/scope_* does.
    general_employer_id = args.get("emp") or None
    general_position = None
    position_raw = args.get("position") or None
    if position_raw and "::" in position_raw:
        general_position = tuple(position_raw.split("::", 1))

    filters = {
        "first": args.get("first") or None,
        "last": args.get("last") or None,
        "middle": args.get("middle") or None,
        "sector": args.get("sector") or None,
        "year": _parse_year(args.get("year")),
        "include_inactive": args.get("status") == "all",
        "employer_id": scope_employer_id or general_employer_id,
        "position": scope_position or general_position,
    }
    searched = any(v for k, v in filters.items() if k != "include_inactive")
    outcome = search_employees(**filters) if searched else None

    comp_range = None
    if outcome and outcome.results:
        comps = [r.current_total_comp for r in outcome.results]
        comp_range = (min(comps), max(comps))

    sector_overview = None
    employers_for_filter = None
    if not scoped:
        sector_overview = sector_population_overview()
        max_employees = max((s["n_employees"] for s in sector_overview), default=0)
        for i, s in enumerate(sector_overview):
            s["pct_of_max"] = round(s["n_employees"] / max_employees * 100, 1) if max_employees else 0
            s["pct_new"] = round(s["n_new"] / s["n_employees"] * 100, 1) if s["n_employees"] else 0
            s["pct_attrition"] = round(s["n_attrition"] / s["n_prior_year"] * 100, 1) if s["n_prior_year"] else 0
            s["color"] = SECTOR_COLORS[i % len(SECTOR_COLORS)]
        employers_for_filter = list_employers_for_filter()

    preselected_positions = list_positions_for_employer(general_employer_id) if general_employer_id else []

    return render_template(
        "search.html", searched=searched, outcome=outcome, sectors=list_sectors(), comp_range=comp_range,
        scope_employer_id=scope_employer_id, scope_sector_id=scope_sector_id, scope_title_norm=scope_title_norm,
        scope_label=scope_label, sector_overview=sector_overview, employers_for_filter=employers_for_filter,
        general_employer_id=general_employer_id, general_position=general_position,
        preselected_positions=preselected_positions,
    )


@bp.route("/employee/<employee_id>")
def profile_page(employee_id):
    profile = get_employee_profile(employee_id)
    if profile is None:
        return render_template("not_found.html", what="employee", key=employee_id), 404
    return render_template("employee.html", profile=profile)
