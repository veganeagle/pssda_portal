import csv
import io

from flask import Blueprint, Response, abort, render_template, request, url_for

from access.employee_profile import get_employee_profile
from access.employee_search import (
    list_sectors, search_employees, search_employees_all, sector_population_overview,
)
from access.employer_position_profile import list_positions_for_employer
from access.employer_profile import list_employers_for_filter
from access.position_profile import list_positions
from web_app.export_limit import EXPORT_PROFILES_PER_HOUR, check_and_record_export

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

    include_inactive = args.get("status") == "all"
    general_sector_id = args.get("sector") or None
    try:
        page = max(1, int(args.get("page", 1)))
    except ValueError:
        page = 1
    filters = {
        "first": args.get("first") or None,
        "last": args.get("last") or None,
        "middle": args.get("middle") or None,
        "sector": general_sector_id,
        "year": _parse_year(args.get("year")),
        "include_inactive": include_inactive,
        "employer_id": scope_employer_id or general_employer_id,
        "position": scope_position or general_position,
        "page": page,
    }
    searched = any(v for k, v in filters.items() if k not in ("include_inactive", "page"))
    outcome = search_employees(**filters) if searched else None

    # For Prev/Next and the "export full list" link — every current filter
    # except `page` itself, so paging/exporting never silently drops a name
    # or status filter the way a bare url_for(sector=...) link would.
    pagination_args = {k: v for k, v in request.args.items() if k != "page"}
    prev_url = next_url = export_url = None
    if outcome and outcome.page_size:
        if outcome.page > 1:
            prev_url = url_for("employee.search", page=outcome.page - 1, **pagination_args)
        if outcome.page * outcome.page_size < outcome.total_count:
            next_url = url_for("employee.search", page=outcome.page + 1, **pagination_args)
        export_url = url_for("employee.export_csv", **pagination_args)

    comp_range = None
    if outcome and outcome.results:
        comps = [r.current_total_comp for r in outcome.results]
        comp_range = (min(comps), max(comps))

    sector_overview = None
    employers_for_filter = None
    if not scoped:
        sector_overview = [dict(s) for s in sector_population_overview()]  # cached; copy before adding keys
        max_employees = max((s["n_employees"] for s in sector_overview), default=0)
        for i, s in enumerate(sector_overview):
            s["pct_of_max"] = round(s["n_employees"] / max_employees * 100, 1) if max_employees else 0
            s["pct_new"] = round(s["n_new"] / s["n_employees"] * 100, 1) if s["n_employees"] else 0
            s["pct_attrition"] = round(s["n_attrition"] / s["n_prior_year"] * 100, 1) if s["n_prior_year"] else 0
            s["color"] = SECTOR_COLORS[i % len(SECTOR_COLORS)]
        employers_for_filter = list_employers_for_filter(active_only=not include_inactive)

    # Position no longer requires an Employer to be picked first: with an
    # employer chosen, scope to that employer's own roles; with just a
    # sector, scope to every role in it (any employer); with neither, show
    # every normalized position province-wide — same fallback a bare
    # Employer="Any" search already supported on the backend, the dropdown
    # just wasn't offering it.
    position_scope_is_global = False
    if general_employer_id:
        preselected_positions = list_positions_for_employer(general_employer_id)
    elif general_sector_id:
        preselected_positions = [p for p in list_positions() if p.sector_id == general_sector_id]
    else:
        preselected_positions = list_positions()
        position_scope_is_global = True

    return render_template(
        "search.html", searched=searched, outcome=outcome, sectors=list_sectors(), comp_range=comp_range,
        scope_employer_id=scope_employer_id, scope_sector_id=scope_sector_id, scope_title_norm=scope_title_norm,
        scope_label=scope_label, sector_overview=sector_overview, employers_for_filter=employers_for_filter,
        general_employer_id=general_employer_id, general_position=general_position,
        general_sector_id=general_sector_id,
        preselected_positions=preselected_positions, position_scope_is_global=position_scope_is_global,
        prev_url=prev_url, next_url=next_url, export_url=export_url,
    )


@bp.route("/employee/<employee_id>")
def profile_page(employee_id):
    profile = get_employee_profile(employee_id)
    if profile is None:
        return render_template("not_found.html", what="employee", key=employee_id), 404
    return render_template("employee.html", profile=profile)


@bp.route("/search/export")
def export_csv():
    """Full-list CSV for an employer-scoped search — only reachable once a
    search is already bounded to one employer (same employer_id/emp param
    the page itself uses), and rate-limited in profiles delivered, not
    requests, since that's the actual bulk-export surface (see
    web_app/export_limit.py)."""
    args = request.args
    scope_employer_id = args.get("employer_id") or None
    scope_sector_id = args.get("scope_sector_id") or None
    scope_title_norm = args.get("scope_title_norm") or None
    scope_position = (scope_sector_id, scope_title_norm) if scope_sector_id and scope_title_norm else None
    general_employer_id = args.get("emp") or None
    general_position = None
    position_raw = args.get("position") or None
    if position_raw and "::" in position_raw:
        general_position = tuple(position_raw.split("::", 1))

    employer_id = scope_employer_id or general_employer_id
    if not employer_id:
        abort(400, "Full-list export requires a specific employer to be selected.")

    rows = search_employees_all(
        first=args.get("first") or None, last=args.get("last") or None, middle=args.get("middle") or None,
        sector=args.get("sector") or None, year=_parse_year(args.get("year")),
        include_inactive=args.get("status") == "all",
        employer_id=employer_id, position=scope_position or general_position,
    )

    if not check_and_record_export(request.remote_addr or "unknown", len(rows)):
        return Response(
            "Export limit reached for this hour — whole-employer CSV exports are capped at "
            f"{EXPORT_PROFILES_PER_HOUR:,} profiles per hour per visitor. Try again later, or browse "
            "the paginated list on the search page instead.",
            status=429, mimetype="text/plain",
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Current title", "Current employer", "Total comp", "First seen", "Last seen"])
    for r in rows:
        writer.writerow([
            f"{r.first_name} {r.last_name}", r.current_job_title, r.current_employer_name,
            f"{r.current_total_comp:.0f}", r.first_seen_year, r.last_seen_year,
        ])
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="employees-at-{employer_id}.csv"'},
    )
