from flask import Blueprint, Response, render_template, url_for

from access.employer_profile import list_employers_for_filter
from access.home_dashboard import get_home_dashboard
from access.sector_profile import list_sectors_for_picker
from web_app.data_dictionary import SECTIONS, TERMS

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
        jsonld=_dataset_jsonld(dashboard.trend[0].year, dashboard.current_year),
    )


@bp.route("/data-dictionary")
def data_dictionary():
    dashboard = get_home_dashboard()
    return render_template(
        "data_dictionary.html", sections=SECTIONS,
        jsonld=_dataset_jsonld(dashboard.trend[0].year, dashboard.current_year),
    )


def _dataset_jsonld(first_year: int, last_year: int) -> dict:
    """schema.org Dataset, for Google Dataset Search. No license is claimed:
    none has been decided for OPSCI's derived data."""
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "OPSCI: Ontario public-sector salary disclosures, linked across years",
        "description": (
            f"Ontario's public-sector salary disclosures (the Sunshine List) for {first_year} to {last_year}, "
            "with individual records linked across years, related job titles grouped within each sector, and "
            "derived measures by employer, job group and sector: disclosed employees, total disclosed salary, "
            "median and 90th-percentile salary, and same-person year-over-year raises. Linking and other "
            "derived measures are estimates."
        ),
        "url": url_for("pages.about_the_data", _external=True),
        "keywords": ["Ontario", "Sunshine List", "public sector salaries", "public sector compensation",
                     "salary disclosure", "Public Sector Salary Disclosure Act"],
        "temporalCoverage": f"{first_year}/{last_year}",
        "spatialCoverage": {"@type": "Place", "name": "Ontario, Canada"},
        "isAccessibleForFree": True,
        "isBasedOn": "https://www.ontario.ca/page/public-sector-salary-disclosure",
        "variableMeasured": TERMS,
        "creator": {"@type": "Organization", "name": "kdsay labs inc.", "url": "https://kdsay.com/"},
    }


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
    "pages.about", "pages.about_the_data", "pages.data_dictionary", "pages.contact", "pages.privacy", "pages.terms",
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
