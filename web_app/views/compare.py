from flask import Blueprint, render_template, request

from access.comparison import compare_employers, compare_positions

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
    return render_template("compare_employer.html", comparison=comparison, trend_json=_trend_json(comparison))


@bp.route("/compare/position")
def position():
    sector_id = request.args.get("sector")
    title_norm = request.args.get("title")
    a = request.args.get("a")
    b = request.args.get("b")
    if not (sector_id and title_norm and a and b):
        return render_template("not_found.html", what="comparison", key="missing position/employer"), 404
    comparison = compare_positions(sector_id, title_norm, a, b)
    return render_template("compare_position.html", comparison=comparison, trend_json=_trend_json(comparison))
