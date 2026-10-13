from flask import Blueprint, render_template

from access.inflation import jobs_vs_inflation, sectors_vs_threshold, threshold_by_year
from access.metro_areas import ONTARIO_POPULATION, job_comparison, metro_overview, role_comparison
from access.regions import location_premiums

bp = Blueprint("insights", __name__)


@bp.route("/insights")
def index():
    last = threshold_by_year()[-1]
    sectors = {s["sector_id"]: s for s in sectors_vs_threshold()}
    jobs = jobs_vs_inflation()
    inflation = {
        "year": last["year"], "threshold": last["threshold"], "disclosed": last["disclosed"], "above": last["above"],
        "schools": sectors["10"], "universities": sectors["11"],
        "behind": sum(1 for j in jobs["jobs"] if j["windows"][0]["enough"] and j["windows"][0]["real"] < 0),
        "jobs": len(jobs["jobs"]), "since": jobs["windows"][0]["start"],
    }

    areas = metro_overview()
    constable = job_comparison("CONSTABLE")
    densest = max(constable["areas"], key=lambda a: a["per_10k"])
    cao = role_comparison("chief-administrative-officer")["people"][0]
    metro = {
        "areas": len(areas), "share": sum(a["population"] for a in areas) / ONTARIO_POPULATION,
        "constable_top": constable["areas"][0], "constable_densest": densest, "cao": cao,
    }

    lp = location_premiums()
    top = max((p for ps in lp["premiums"].values() for p in ps), key=lambda p: p["premium"])
    regional = {"year": lp["year"], "top": top, "uniform": lp["uniform"]}
    return render_template("insights.html", inflation=inflation, metro=metro, regional=regional)
