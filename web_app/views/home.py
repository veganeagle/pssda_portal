from flask import Blueprint, render_template

from access.home_dashboard import get_home_dashboard
from access.sector_profile import list_sectors_for_picker
from web_app.formatting import proper_case

bp = Blueprint("home", __name__)

# Display-only grouping for the "where the money goes" donut — these are too
# close in size/mandate to read as separate slices at a glance, or (for the
# three Government of Ontario sectors) are really one employer wearing
# different hats. The underlying sector breakdown (access.home_dashboard)
# stays ungrouped; this is purely how this one chart presents it.
_DONUT_MERGE = {
    "UNIVERSITIES": "Universities & Colleges",
    "COLLEGES": "Universities & Colleges",
    "CROWN AGENCIES": "Other Public Service",
    "OTHER PUBLIC SERVICE": "Other Public Service",
    "GOVERNMENT OF ONTARIO MINISTRIES": "Government of Ontario",
    "GOVERNMENT OF ONTARIO JUDICIARY": "Government of Ontario",
    "GOVERNMENT OF ONTARIO LEGISLATIVE ASSEMBLY AND OFFICES": "Government of Ontario",
}


def _donut_sectors(sectors):
    merged: dict[str, dict] = {}
    for s in sectors:
        label = _DONUT_MERGE.get(s.sector_name, proper_case(s.sector_name))
        bucket = merged.setdefault(label, {"sector_name": label, "total_payroll": 0.0, "headcount": 0})
        bucket["total_payroll"] += s.total_payroll
        bucket["headcount"] += s.headcount
    return sorted(merged.values(), key=lambda d: d["total_payroll"], reverse=True)


@bp.route("/")
def index():
    dashboard = get_home_dashboard()
    dashboard_json = {
        "trend": [t.model_dump() for t in dashboard.trend],
        "sectors": _donut_sectors(dashboard.sectors),
    }
    return render_template(
        "home.html", dashboard=dashboard, dashboard_json=dashboard_json, sectors=list_sectors_for_picker(),
    )
