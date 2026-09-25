from flask import Blueprint, render_template

from access.employer_position_profile import get_employer_position_profile

bp = Blueprint("combo", __name__)


@bp.route("/employer/<employer_id>/position/<sector_id>/<title_norm>")
def profile_page(employer_id, sector_id, title_norm):
    combo = get_employer_position_profile(employer_id, sector_id, title_norm)
    if combo is None:
        return render_template("not_found.html", what="employer/position combination", key=f"{employer_id}/{sector_id}/{title_norm}"), 404
    return render_template("combo.html", combo=combo)
