import math

from flask import Blueprint, render_template

from access.inflation import (
    MIN_COMPARED, ONTARIO_CPI, THRESHOLD, THRESHOLD_YEAR, indexed_threshold, jobs_vs_inflation, sectors_vs_threshold,
    threshold_by_year,
)

bp = Blueprint("inflation", __name__)

W, H, LEFT, RIGHT, TOP, BOTTOM = 760, 300, 56, 70, 14, 26
THRESHOLD_AXIS = (100_000, 200_000)


def _threshold_chart(rows: list[dict]) -> dict:
    """Stacked bars (above the indexed threshold at the bottom, the rest on top)
    on a count axis, and the indexed threshold as a line on a dollar axis."""
    step = 100_000
    top_count = math.ceil(max(r["disclosed"] for r in rows) / step) * step
    plot_w, plot_h = W - LEFT - RIGHT, H - TOP - BOTTOM
    slot = plot_w / len(rows)
    bar_w = slot * 0.62

    def y_count(v):
        return round(TOP + plot_h * (1 - v / top_count), 1)

    def y_dollars(v):
        lo, hi = THRESHOLD_AXIS
        return round(TOP + plot_h * (1 - (v - lo) / (hi - lo)), 1)

    bars = []
    for i, r in enumerate(rows):
        x = LEFT + slot * i + (slot - bar_w) / 2
        bars.append(r | {
            "x": round(x, 1), "w": round(bar_w, 1), "cx": round(x + bar_w / 2, 1),
            "y_total": y_count(r["disclosed"]), "y_above": y_count(r["above"]), "y_line": y_dollars(r["threshold"]),
            "below": r["disclosed"] - r["above"], "above_label": f"{r['above'] / 1000:.0f}K",
        })
    return {
        "w": W, "h": H, "left": LEFT, "right": W - RIGHT, "top": TOP, "bottom": H - BOTTOM, "bars": bars,
        "line": " ".join(f"{b['cx']},{b['y_line']}" for b in bars),
        "count_ticks": [{"y": y_count(v), "label": f"{v // 1000:,}K"} for v in range(0, top_count + 1, step)],
        "dollar_ticks": [{"y": y_dollars(v), "label": f"${v // 1000}K"} for v in range(THRESHOLD_AXIS[0], THRESHOLD_AXIS[1] + 1, 25_000)],
    }


@bp.route("/inflation")
def index():
    rows = threshold_by_year()
    first, last = rows[0], rows[-1]
    jobs = jobs_vs_inflation()
    behind = [sum(1 for j in jobs["jobs"] if j["windows"][i]["enough"] and j["windows"][i]["real"] < 0)
              for i in range(len(jobs["windows"]))]
    sectors = sectors_vs_threshold()
    widest = max(s["disclosed"] for s in sectors)
    sectors = [s | {"pct_bar": s["disclosed"] / widest * 100, "pct_above": s["above"] / widest * 100} for s in sectors]
    return render_template(
        "inflation.html", sectors=sectors, chart=_threshold_chart(rows), first=first, last=last, jobs=jobs, behind=behind,
        threshold=THRESHOLD, threshold_year=THRESHOLD_YEAR, cpi=ONTARIO_CPI,
        threshold_2010=indexed_threshold(first["year"]), min_compared=MIN_COMPARED,
    )
