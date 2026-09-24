"""Basic per-IP request throttle. Not a security boundary — the underlying
disclosure data is already public — just a guard against a single source
hammering the app or bulk-scraping the enriched dataset (entity resolution,
multi-year linking, computed metrics) at scale.

Single-process, in-memory storage: fine for one small VM, resets on restart,
and does NOT coordinate across multiple worker processes — switch
storage_uri to a shared backend (e.g. Redis) first if this ever runs with
more than one worker.
"""
from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

REQUESTS_PER_HOUR = 300  # generous for real browsing, bounds scripted bulk pulls


def _is_static_request() -> bool:
    return request.endpoint == "static"


limiter = Limiter(
    key_func=get_remote_address,
    # application_limits = one shared counter per IP across every route.
    # default_limits would instead give each route its own separate budget,
    # which isn't "one source hitting the site a lot" — it's easy to get
    # backwards, so don't swap this without re-testing across >1 route.
    application_limits=[f"{REQUESTS_PER_HOUR} per hour"],
    application_limits_exempt_when=_is_static_request,
    storage_uri="memory://",
)
