from flask import Blueprint, render_template

from access.position_profile import get_position_profile

bp = Blueprint("position", __name__)


@bp.route("/position/<sector_id>/<title_norm>")
def profile_page(sector_id, title_norm):
    position = get_position_profile(sector_id, title_norm)
    if position is None:
        return render_template("not_found.html", what="position", key=f"{sector_id}/{title_norm}"), 404
    return render_template("position.html", position=position)
