from flask import Blueprint, render_template

from access.sector_profile import get_sector_profile, list_sectors_for_picker
from access.top_earners import search_top_earners
from web_app.formatting import proper_case

bp = Blueprint("sector", __name__)


@bp.route("/sector/<sector_id>")
def profile_page(sector_id):
    sector = get_sector_profile(sector_id)
    if sector is None:
        return render_template("not_found.html", what="sector", key=sector_id), 404
    top_earners = search_top_earners(sector_id=sector_id, limit=20)
    trend_json = [t.model_dump() for t in sector.trend]
    position_mix_json = [
        {"name": proper_case(m.title_norm), "value": m.headcount, "label": f"{m.headcount:,}"}
        for m in sector.position_mix
    ]
    return render_template(
        "sector.html", sector=sector, top_earners=top_earners, sectors=list_sectors_for_picker(),
        trend_json=trend_json, position_mix_json=position_mix_json,
    )
