import math

from flask import Blueprint, render_template, request

from access.employee_search import list_sectors
from access.employer_profile import list_employers_for_filter
from access.position_profile import get_position_profile, search_positions, sector_position_overview
from access.regions import MIN_REGION_COUNT, position_by_region
from access.salary_distribution import salary_distribution
from access.sector_profile import get_sector_profile
from succession.access import feeders
from web_app.formatting import proper_case

bp = Blueprint("position", __name__)

# Same cycle as charts.js's DONUT_COLORS, so a sector's dot here reads as
# the same family of color used in donut charts elsewhere on the site.
SECTOR_COLORS = [
    "#2f6f6b", "#b8831e", "#6b8f3f", "#8b5fb8", "#c2574a",
    "#3f7fb8", "#9a8f3f", "#5f8f8f", "#b85f8f", "#7a7a7a", "#4f6f9f",
]

REGION_TICK_STEPS = [5_000, 10_000, 20_000, 25_000, 50_000, 100_000]  # first giving <= 6 ticks


def _region_chart(data: dict) -> dict | None:
    """Range-chart geometry for the regional chart: every value as a % position
    on one shared dollar axis, fitted to the data (not zero-based) so regional
    gaps stay visible. None unless at least two regions have enough people."""
    shown = [r for r in data["regions"] if r["n"] >= MIN_REGION_COUNT]
    if len(shown) < 2:
        return None
    lows = [r["p10"] for r in shown] + [data["ontario"]["p10"]]
    highs = [r["p90"] for r in shown] + [data["ontario"]["p90"]]
    step = next((s for s in REGION_TICK_STEPS if (max(highs) - min(lows)) / s <= 6), REGION_TICK_STEPS[-1])
    lo = math.floor(min(lows) / step) * step
    hi = math.ceil(max(highs) / step) * step

    def pos(v):
        return round((v - lo) / (hi - lo) * 100, 2)

    ontario = data["ontario"]
    rows = []
    for r in data["regions"]:
        row = {"region": r["region"], "n": r["n"], "enough": r["n"] >= MIN_REGION_COUNT}
        if row["enough"]:
            row |= {
                "p10": r["p10"], "median": r["median"], "p90": r["p90"],
                "bar_left": pos(r["p10"]), "bar_width": round(pos(r["p90"]) - pos(r["p10"]), 2),
                "median_pos": pos(r["median"]), "diff": r["median"] - ontario["median"],
            }
        rows.append(row)
    return {
        "rows": rows,
        "ticks": [{"label": f"${v // 1000:,}K", "pos": pos(v)} for v in range(int(lo), int(hi) + 1, step)],
        "ontario_median": ontario["median"], "ontario_pos": pos(ontario["median"]),
        # Only worth a note when it's a real share (e.g. hospital roles at
        # province-wide agencies), not a handful of people.
        "n_unlocated": data["n_unlocated"] if data["n_unlocated"] / ontario["n"] >= 0.01 else 0,
        "pct_unlocated": data["n_unlocated"] / ontario["n"],
        "min_region_count": MIN_REGION_COUNT,
    }


@bp.route("/positions")
def search():
    title = request.args.get("title") or None
    sector = request.args.get("sector") or None
    employer = request.args.get("emp") or None
    results = search_positions(title_contains=title, sector_id=sector, employer_id=employer)

    sector_overview = sector_position_overview()
    max_headcount = max((s["total_headcount"] for s in sector_overview), default=0)
    for i, s in enumerate(sector_overview):
        s["pct_of_max"] = round(s["total_headcount"] / max_headcount * 100, 1) if max_headcount else 0
        s["pct_mapped"] = round(s["normed_headcount"] / s["total_headcount"] * 100, 1) if s["total_headcount"] else 0
        s["color"] = SECTOR_COLORS[i % len(SECTOR_COLORS)]

    # A selected sector swaps the all-sector overview for a compact view of
    # that sector (fastest movers + position mix), drawn from the sector
    # dashboard's own data.
    sector_view = get_sector_profile(sector) if sector else None
    position_mix_json = [
        {"name": proper_case(m.title_norm), "value": m.headcount, "label": f"{m.headcount:,}"}
        for m in sector_view.position_mix
    ] if sector_view else None

    return render_template(
        "positions_search.html", results=results, sectors=list_sectors(), sector_overview=sector_overview,
        employers_for_filter=list_employers_for_filter(), employer=employer,
        sector_view=sector_view, position_mix_json=position_mix_json,
    )


@bp.route("/position/<sector_id>/<title_norm>")
def profile_page(sector_id, title_norm):
    position = get_position_profile(sector_id, title_norm)
    if position is None:
        return render_template("not_found.html", what="position", key=f"{sector_id}/{title_norm}"), 404
    trend_json = [
        {"year": h.year, "headcount": h.headcount, "median_salary": h.median_salary}
        for h in sorted(position.history, key=lambda h: h.year)
    ]
    salary_bands = salary_distribution(position.current.year, sector_id=sector_id, title_norm=title_norm)
    region_chart = _region_chart(position_by_region(sector_id, title_norm, position.current.year))
    return render_template(
        "position.html", position=position, trend_json=trend_json, salary_bands=salary_bands,
        region_chart=region_chart, feeders=feeders(sector_id, title_norm),
    )
