from flask import Blueprint, render_template, request

from access.comparison import compare_employers, compare_positions, list_comparable_employers_for_position
from access.employer_profile import list_employers_for_filter
from access.salary_distribution import salary_distribution
from access.sector_profile import list_sectors_for_picker

bp = Blueprint("compare", __name__)


def _trend_json(comparison):
    return {
        "a": [t.model_dump() for t in comparison.a.trend],
        "b": [t.model_dump() for t in comparison.b.trend],
    }


def _compare_bands(bands_a, bands_b):
    """Pairs the two sides' salary bands for one grouped chart. Bars show each
    side's share of its own disclosed employees, so a large and a small
    employer compare on shape rather than size; one scale across both sides."""
    total_a = sum(b["n"] for b in bands_a)
    total_b = sum(b["n"] for b in bands_b)
    rows = [
        {"label": a["label"], "n_a": a["n"], "n_b": b["n"],
         "share_a": a["n"] / total_a if total_a else 0, "share_b": b["n"] / total_b if total_b else 0}
        for a, b in zip(bands_a, bands_b)
    ]
    max_share = max(max(r["share_a"], r["share_b"]) for r in rows) or 1
    for r in rows:
        r["pct_a"] = round(r["share_a"] / max_share * 100, 1)
        r["pct_b"] = round(r["share_b"] / max_share * 100, 1)
    return rows


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
    salary_bands = _compare_bands(
        salary_distribution(comparison.a.current_year, employer_id=a),
        salary_distribution(comparison.b.current_year, employer_id=b),
    )
    return render_template(
        "compare_employer.html", comparison=comparison, trend_json=_trend_json(comparison), salary_bands=salary_bands,
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
    salary_bands = _compare_bands(
        salary_distribution(comparison.a.current_year, employer_id=a, sector_id=sector_id, title_norm=title_norm),
        salary_distribution(comparison.b.current_year, employer_id=b, sector_id=sector_id, title_norm=title_norm),
    )
    return render_template(
        "compare_position.html", comparison=comparison, trend_json=_trend_json(comparison), salary_bands=salary_bands,
        other_employers=other_employers,
    )
