from flask import Blueprint, render_template

from access.home_dashboard import get_home_dashboard

bp = Blueprint("pages", __name__)

CONTACT_EMAIL = "support@kdsay.com"


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/about-the-data")
def about_the_data():
    dashboard = get_home_dashboard()
    return render_template(
        "about_the_data.html", first_year=dashboard.trend[0].year, current_year=dashboard.current_year,
    )


@bp.route("/contact")
def contact():
    return render_template("contact.html", contact_email=CONTACT_EMAIL)


@bp.route("/privacy")
def privacy():
    return render_template("privacy.html", contact_email=CONTACT_EMAIL)


@bp.route("/terms")
def terms():
    return render_template("terms.html")
