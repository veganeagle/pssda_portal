import math

from flask import Blueprint, render_template

from access.metro_areas import (
    BENCHMARK_ROLES, LEADERSHIP_ROLES, MIN_BENCHMARK_N, ONTARIO_POPULATION, area_benchmarks, area_employers,
    area_leadership, area_pay_growth, area_summary, job_comparison, metro_overview, role_comparison, role_slug,
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


TICK_STEPS = [5_000, 10_000, 20_000, 25_000, 50_000, 100_000, 200_000]  # first giving <= 6 ticks


def _ticks(lo_value: float, hi_value: float) -> tuple[float, float, int]:
    step = next((s for s in TICK_STEPS if (hi_value - lo_value) / s <= 6), TICK_STEPS[-1])
    return math.floor(lo_value / step) * step, math.ceil(hi_value / step) * step, step


def _range_chart(job: dict) -> dict:
    """P10-P90 bar, median diamond and Ontario median line per area, as %
    positions on one shared dollar axis fitted to the data."""
    shown = [a for a in job["areas"] if a["enough"]] + [job["ontario"]]
    lo, hi, step = _ticks(min(a["p10"] for a in shown), max(a["p90"] for a in shown))

    def pos(v):
        return round((v - lo) / (hi - lo) * 100, 2)

    for a in job["areas"]:
        if a["enough"]:
            a |= {"bar_left": pos(a["p10"]), "bar_width": round(pos(a["p90"]) - pos(a["p10"]), 2), "median_pos": pos(a["median"])}
    return {
        "ticks": [{"label": f"${v // 1000:,}K", "pos": pos(v)} for v in range(int(lo), int(hi) + 1, step)],
        "ontario_pos": pos(job["ontario"]["median"]),
    }


def _scatter(people: list[dict]) -> dict:
    """Salary against population served (log scale) on a 600 x 320 viewBox."""
    pts = [p for p in people if p["plotted"] and p["population"]]
    w, h, left, bottom, top, right = 600, 320, 58, 34, 12, 14
    lx = [math.log10(p["population"]) for p in pts]
    x0, x1 = math.floor(min(lx) * 2) / 2, math.ceil(max(lx) * 2) / 2
    y0, y1, step = _ticks(min(p["salary_paid"] for p in pts), max(p["salary_paid"] for p in pts))

    def sx(v):
        return round(left + (math.log10(v) - x0) / (x1 - x0) * (w - left - right), 1)

    def sy(v):
        return round(h - bottom - (v - y0) / (y1 - y0) * (h - bottom - top), 1)

    x_ticks = [10 ** e for e in range(math.ceil(x0), math.floor(x1) + 1)]
    x_ticks = sorted({t * m for t in x_ticks for m in (1, 3) if x0 <= math.log10(t * m) <= x1})
    return {
        "w": w, "h": h, "left": left, "right": w - right, "top": top, "bottom": h - bottom,
        "points": [p | {"cx": sx(p["population"]), "cy": sy(p["salary_paid"])} for p in pts],
        "x_ticks": [{"x": sx(t), "label": f"{t / 1e6:g}M" if t >= 1e6 else f"{t / 1e3:g}K"} for t in x_ticks],
        "y_ticks": [{"y": sy(v), "label": f"${v // 1000:,}K"} for v in range(int(y0), int(y1) + 1, step)],
    }


@bp.route("/metro")
def index():
    areas = metro_overview()
    max_headcount = max(a["headcount"] for a in areas)
    for a in areas:
        a["pct_of_max"] = round(a["headcount"] / max_headcount * 100, 1)
        a["col"], a["row"], a["short"] = TILE_LAYOUT[a["slug"]]
    jobs = []
    for title, _ in BENCHMARK_ROLES:
        j = job_comparison(title)
        top = j["areas"][0]
        jobs.append({"title_norm": title, "ontario_median": j["ontario"]["median"], "n": j["ontario"]["n"],
                     "top_name": top["name"], "top_median": top["median"]})
    roles = []
    for label, _ in LEADERSHIP_ROLES:
        r = role_comparison(role_slug(label))
        top = r["people"][0]
        roles.append({"slug": r["slug"], "label": label, "employers": len(r["people"]), "top": top})
    return render_template(
        "metro.html", areas=areas, year=areas[0]["year"], jobs=jobs, roles=roles,
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


@bp.route("/metro/job/<title_norm>")
def job(title_norm):
    data = job_comparison(title_norm)
    if data is None:
        return render_template("not_found.html", what="metro benchmark job", key=title_norm), 404
    return render_template("metro_job.html", job=data, chart=_range_chart(data), min_benchmark_n=MIN_BENCHMARK_N)


@bp.route("/metro/role/<slug>")
def role(slug):
    data = role_comparison(slug)
    if data is None:
        return render_template("not_found.html", what="metro leadership role", key=slug), 404
    return render_template("metro_role.html", role=data, scatter=_scatter(data["people"]))
