from flask import Blueprint, render_template

from access.regions import (
    PREMIUM_MIN, PREMIUM_MIN_ONTARIO_N, PREMIUM_MIN_REGION_N, REGIONS, TREND_END_YEARS, TREND_YEARS, UNIFORM_MAX_SPREAD,
    location_premiums, regional_trends, sector_region_overview,
)

bp = Blueprint("regions", __name__)


def _trend_chart(t: dict) -> dict:
    """SVG polylines on a 0-100 x 0-40 viewBox (stretched to the card; strokes
    don't scale), shared y-range across the four regions, with the 1.0
    'same as Ontario' baseline."""
    points = [p for s in t["series"].values() for p in s]
    years = [p["year"] for p in points]
    lo = min([p["ratio"] for p in points] + [1.0])
    hi = max([p["ratio"] for p in points] + [1.0])
    pad = (hi - lo) * 0.1 or 0.05
    lo, hi = lo - pad, hi + pad
    x0, x1 = min(years), max(years)

    def xy(p):
        return f"{(p['year'] - x0) / (x1 - x0) * 100:.1f},{(hi - p['ratio']) / (hi - lo) * 40:.1f}"

    lines = [
        {"region": r, "points": " ".join(xy(p) for p in t["series"][r]), "highlight": r == t["region"]}
        for r in REGIONS if r in t["series"]
    ]
    lines.sort(key=lambda l: l["highlight"])  # highlighted region drawn last, on top
    return {
        **t, "lines": lines, "first_premium": t["first_ratio"] - 1, "last_premium": t["last_ratio"] - 1, "first_year": x0, "last_year": x1,
        "baseline_y": round((hi - 1.0) / (hi - lo) * 40, 1),
        "top_label": f"{hi - 1:+.0%}", "bottom_label": f"{lo - 1:+.0%}",
    }


@bp.route("/regions")
def index():
    lp = location_premiums()
    overview_rows = sector_region_overview()
    sectors: dict[str, dict] = {}
    for r in overview_rows:
        s = sectors.setdefault(r["sector_id"], {"sector_id": r["sector_id"], "sector_name": r["sector_name"], "cells": {}})
        s["cells"][r["region"]] = r | {"median_k": r["median_salary"] / 1000}
    # Only sectors with regional employers; ministries, OPG etc. are all province-wide.
    overview = [s for s in sectors.values() if set(s["cells"]) - {"NONE"}]
    return render_template(
        "regions.html", year=lp["year"], prior_year=lp["year"] - 1, premiums=lp["premiums"], uniform=lp["uniform"],
        trends=[_trend_chart(t) for t in regional_trends()], regions=REGIONS,
        first_period=f"{lp['year'] - TREND_YEARS}–{(lp['year'] - TREND_YEARS + TREND_END_YEARS - 1) % 100:02d}",
        last_period=f"{lp['year'] - TREND_END_YEARS + 1}–{lp['year'] % 100:02d}",
        overview=overview, overview_columns=REGIONS + ["NONE"],
        premium_min=PREMIUM_MIN, premium_min_region_n=PREMIUM_MIN_REGION_N,
        premium_min_ontario_n=PREMIUM_MIN_ONTARIO_N, uniform_max_spread=UNIFORM_MAX_SPREAD, trend_years=TREND_YEARS,
    )
