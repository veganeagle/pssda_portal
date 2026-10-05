from flask import Blueprint, Response, render_template, url_for

from access.employer_profile import list_employers_for_filter
from access.home_dashboard import get_home_dashboard
from access.sector_profile import list_sectors_for_picker

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


# ---- crawler files: see web_app/seo.py for what is and isn't indexable ----

_SITEMAP_STATIC = [
    "home.index", "position.search", "employer.search", "employee.search", "top_earners.index",
    "pages.about", "pages.about_the_data", "pages.contact", "pages.privacy", "pages.terms",
]


@bp.route("/robots.txt")
def robots_txt():
    return Response(render_template("robots.txt"), mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap_xml():
    urls = [url_for(endpoint, _external=True) for endpoint in _SITEMAP_STATIC]
    urls += [url_for("sector.profile_page", sector_id=s["sector_id"], _external=True) for s in list_sectors_for_picker()]
    urls += [url_for("employer.profile_page", employer_id=e["employer_id"], _external=True)
             for e in list_employers_for_filter(active_only=False)]
    return Response(render_template("sitemap.xml", urls=urls), mimetype="application/xml")


@bp.route("/llms.txt")
def llms_txt():
    return Response(render_template("llms.txt", contact_email=CONTACT_EMAIL), mimetype="text/plain")
