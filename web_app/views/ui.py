from flask import Blueprint, request, render_template
from web_app.services.analytics_service import build_panel_query
from web_app.services.dropdown_service import dropdown_cache
from web_app.config import YEARS_RANGE

bp = Blueprint("ui", __name__)

@bp.route("/")
def home():
    return "<h1>PSSDA Insight Studio</h1><p>Use /compare_live to access the dashboard.</p>"

@bp.route("/compare_live", methods=["GET", "POST"])
def compare_live():
    years = YEARS_RANGE
    grouped, data = {}, False

    dropdowns = {
        "sectors": dropdown_cache["sectors"],
        "employers": dropdown_cache["employers"],
        "regions": dropdown_cache["regions"],
        # dropdown_cache["titles"] has one row per (title, employer, sector,
        # region) combination — dedupe to distinct title strings for the
        # initial (unfiltered) page-load dropdown; /api/titles handles the
        # sector/employer-filtered cascading version separately.
        "titles": sorted({t["Title"] for t in dropdown_cache["titles"] if t.get("Title")}),
    }

    if request.method == "POST":
        # Ignore 'All' and empty values
        filters = {k: v for k, v in request.form.items()
                   if v and v != "All" and not k.startswith("Comp")}
        comp_filters = {k.replace("Comp", ""): v
                        for k, v in request.form.items()
                        if k.startswith("Comp") and v and v != "All"}

        df_base = build_panel_query(filters, years)
        df_comp = build_panel_query(comp_filters, years)

        def fmt(metric, v):
            if v is None:
                return "–"
            if "Salary" in metric or "Benefits" in metric:
                return f"${v:,.0f}"
            if "Percent" in metric:
                return f"{v:.1f}%"
            if "Raise" in metric:
                return f"{v:.2%}"
            return f"{v:,.0f}"

        metrics = [
            ("Headcount", ["CountEmployees", "ReturningEmployees"]),
            ("Compensation", [
                "AvgSalary", "AvgNewSalary", "AvgReturningSalary",
                "AvgRaiseReturning", "AvgTaxableBenefits", "NumEmployers"
            ]),
            ("Demographics", ["PercentFemale"]),
        ]

        grouped = {}
        for group, cols in metrics:
            grouped[group] = {}
            for col in cols:
                base_vals = df_base[col].tolist() if not df_base.empty else [None] * len(years)
                comp_vals = df_comp[col].tolist() if not df_comp.empty else [None] * len(years)
                delta = (comp_vals[-1] or 0) - (base_vals[-1] or 0)
                grouped[group][col] = {
                    "baseline": [fmt(col, v) for v in base_vals],
                    "compare": [fmt(col, v) for v in comp_vals],
                    "delta_display": f"{delta:+,.1f}" if isinstance(delta, (int, float)) else "–",
                    "delta_class": (
                        "delta-pos" if delta > 0
                        else "delta-neg" if delta < 0
                        else "delta-neutral"
                    ),
                }

        data = not df_base.empty or not df_comp.empty

    return render_template(
        "compare_live.html",
        years=years,
        grouped=grouped,
        data=data,
        dropdowns=dropdowns,
    )
