from flask import Blueprint, render_template

from access.metro_areas import (
    MIN_BENCHMARK_N, ONTARIO_POPULATION, area_benchmarks, area_employers, area_leadership, area_pay_growth, area_summary, metro_overview,
)

bp = Blueprint("metro", __name__)

# Tile map of southern Ontario: (column, row, short label), placed by hand so
# neighbours sit roughly where they are; the GTA would overlap on a real map.
TILE_LAYOUT = {
    "simcoe": (5, 0, "Simcoe"), "ottawa": (9, 0, "Ottawa"),
    "waterloo": (2, 1, "Waterloo"), "halton": (3, 1, "Halton"), "peel": (4, 1, "Peel"), "york": (5, 1, "York"),
    "durham": (6, 1, "Durham"),
    "london": (1, 2, "London"), "hamilton": (4, 2, "Hamilton"), "toronto": (5, 2, "Toronto"),
    "windsor": (0, 3, "Windsor"), "niagara": (4, 3, "Niagara"),
}


def _growth_chart(series: list[dict]) -> dict:
    """Area and Ontario raise lines on a 0-100 x 0-40 viewBox, with a 0% baseline."""
    values = [s["area"] for s in series] + [s["ontario"] for s in series] + [0.0]
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.1 or 0.01
    lo, hi = lo - pad, hi + pad
    x0, x1 = series[0]["year"], series[-1]["year"]

    def points(key):
        return " ".join(f"{(s['year'] - x0) / (x1 - x0) * 100:.1f},{(hi - s[key]) / (hi - lo) * 40:.1f}" for s in series)

    return {
        "area": points("area"), "ontario": points("ontario"), "baseline_y": round(hi / (hi - lo) * 40, 1),
        "top_label": f"{hi:+.0%}", "bottom_label": f"{lo:+.0%}", "first_year": x0, "last_year": x1,
    }


@bp.route("/metro")
def index():
    areas = metro_overview()
    max_headcount = max(a["headcount"] for a in areas)
    for a in areas:
        a["pct_of_max"] = round(a["headcount"] / max_headcount * 100, 1)
        a["col"], a["row"], a["short"] = TILE_LAYOUT[a["slug"]]
    return render_template(
        "metro.html", areas=areas, year=areas[0]["year"],
        covered=sum(a["population"] for a in areas), ontario_population=ONTARIO_POPULATION,
    )


@bp.route("/metro/<slug>")
def area(slug):
    summary = area_summary(slug)
    if summary is None:
        return render_template("not_found.html", what="metro area", key=slug), 404
    employers = area_employers(slug)
    for e in employers:
        e["share"] = e["headcount"] / summary["headcount"]
    growth = area_pay_growth(slug)
    return render_template(
        "metro_area.html", a=summary, year=summary["year"], employers=employers,
        benchmarks=area_benchmarks(slug), min_benchmark_n=MIN_BENCHMARK_N,
        growth=growth, growth_chart=_growth_chart(growth["series"]), leadership=area_leadership(slug),
    )
