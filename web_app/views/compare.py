from flask import Blueprint, render_template, request

from access.comparison import compare_employers, compare_positions, list_comparable_employers_for_position
from access.employer_profile import list_employers_for_filter
from access.sector_profile import list_sectors_for_picker

bp = Blueprint("compare", __name__)


def _trend_json(comparison):
    return {
        "a": [t.model_dump() for t in comparison.a.trend],
        "b": [t.model_dump() for t in comparison.b.trend],
    }


@bp.route("/compare/employer")
def employer():
    a = request.args.get("a")
    b = request.args.get("b")
    if not a or not b:
        return render_template("not_found.html", what="comparison", key="missing employer"), 404
    comparison = compare_employers(a, b)
    # Lets the page itself swap out the right-hand side without going back
    # to the employer profile page first — any sector, not just A's, so a
    # cross-sector pairing (e.g. a university vs. a college) can be reached
    # straight from here too.
    all_employers = [e for e in list_employers_for_filter(active_only=True) if e["employer_id"] not in (a, b)]
    return render_template(
        "compare_employer.html", comparison=comparison, trend_json=_trend_json(comparison),
        all_employers=all_employers, sectors=list_sectors_for_picker(),
    )


@bp.route("/compare/position")
def position():
    sector_id = request.args.get("sector")
    title_norm = request.args.get("title")
    a = request.args.get("a")
    b = request.args.get("b")
    if not (sector_id and title_norm and a and b):
        return render_template("not_found.html", what="comparison", key="missing position/employer"), 404
    comparison = compare_positions(sector_id, title_norm, a, b)
    other_employers = [
        e for e in list_comparable_employers_for_position(sector_id, title_norm, a) if e["employer_id"] != b
    ]
    return render_template(
        "compare_position.html", comparison=comparison, trend_json=_trend_json(comparison),
        other_employers=other_employers,
    )
