from flask import Blueprint, render_template

from access.employer_profile import get_employer_profile

bp = Blueprint("employer", __name__)


@bp.route("/employer/<employer_id>")
def profile_page(employer_id):
    employer = get_employer_profile(employer_id)
    if employer is None:
        return render_template("not_found.html", what="employer", key=employer_id), 404
    return render_template("employer.html", employer=employer)
