from flask import Blueprint, request, jsonify
from web_app.services.analytics_service import build_panel_query
from web_app.config import YEARS_RANGE, EXPORT_NAMES_DEFAULT
from web_app.services.dropdown_service import (filter_employers, filter_titles, filter_geography)

bp = Blueprint("api", __name__)

@bp.route("/panel", methods=["POST"])
def panel():
    """Generate 3-year analytics panel."""
    payload = request.get_json(force=True)
    filters = payload.get("filters", {})
    years = payload.get("years", YEARS_RANGE)
    names = payload.get("names", EXPORT_NAMES_DEFAULT)

    df = build_panel_query(filters, years, names)
    return jsonify(df.to_dict(orient="records"))


@bp.route("/api/employers")
def api_employers():
    """Return employers filtered by sector."""
    sector_id = request.args.get("sector_id")
    employers = filter_employers(sector_id)
    employers_sorted = sorted(employers, key=lambda e: e["EmployerName"])
    return jsonify(employers_sorted)

@bp.route("/api/titles")
def api_titles():
    """Return titles filtered by sector/employer."""
    sector_id = request.args.get("sector_id")
    employer_id = request.args.get("employer")
    titles = filter_titles(sector_id, employer_id)
    titles_sorted = sorted([{"JobTitleNorm": t} for t in titles], key=lambda x: x["JobTitleNorm"])
    return jsonify(titles_sorted)


@bp.route("/api/regions")
def api_regions():
    """Return standardized region list (All, Central, East, West, North, Unknown)."""
    region = request.args.get("region")
    geo = request.args.get("geo")
    regions = filter_geography(region, geo)
    regions_sorted = sorted([{"Region": r} for r in regions], key=lambda x: x["Region"])
    return jsonify(regions_sorted)
