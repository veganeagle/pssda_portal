from flask import Blueprint, render_template

from access.comparison import list_comparable_employers_for_position
from access.employer_position_profile import get_employer_position_profile
from access.salary_distribution import salary_distribution

bp = Blueprint("combo", __name__)


@bp.route("/employer/<employer_id>/position/<sector_id>/<title_norm>")
def profile_page(employer_id, sector_id, title_norm):
    combo = get_employer_position_profile(employer_id, sector_id, title_norm)
    if combo is None:
        return render_template("not_found.html", what="employer/position combination", key=f"{employer_id}/{sector_id}/{title_norm}"), 404
    comparable_employers = list_comparable_employers_for_position(sector_id, title_norm, employer_id)
    trend_json = [
        {"year": h.year, "headcount": h.headcount, "median_salary": h.median_salary}
        for h in sorted(combo.history, key=lambda h: h.year)
    ]
    salary_bands = salary_distribution(combo.current.year, employer_id=employer_id, sector_id=sector_id, title_norm=title_norm)
    return render_template(
        "combo.html", combo=combo, comparable_employers=comparable_employers, trend_json=trend_json,
        salary_bands=salary_bands,
    )
