"""Basic per-IP request throttle. Not a security boundary — the underlying
disclosure data is already public — just a guard against a single source
hammering the app or bulk-scraping the enriched dataset (entity resolution,
multi-year linking, computed metrics) at scale.

Single-process, in-memory storage: fine for one small VM, resets on restart,
and does NOT coordinate across multiple worker processes — switch
storage_uri to a shared backend (e.g. Redis) first if this ever runs with
more than one worker.
"""
import socket
from functools import lru_cache

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

REQUESTS_PER_HOUR = 300  # generous for real browsing, bounds scripted bulk pulls


# Search-engine crawlers are exempt, but only once verified the way Google and
# Bing document it: the IP's reverse DNS name is under the engine's own domain,
# and that name resolves forward to the same IP. The User-Agent alone is never
# trusted — anyone can send "Googlebot". Only requests that claim to be a
# crawler are checked, and each IP's result is cached.
_CRAWLER_AGENTS = ("googlebot", "google-inspectiontool", "googleother", "bingbot")
_CRAWLER_DOMAINS = (".googlebot.com", ".google.com", ".search.msn.com")


@lru_cache(maxsize=4096)
def _is_verified_crawler_ip(ip: str) -> bool:
    try:
        host = socket.gethostbyaddr(ip)[0].lower()
        return host.endswith(_CRAWLER_DOMAINS) and ip in socket.gethostbyname_ex(host)[2]
    except OSError:
        return False


def _is_exempt_request() -> bool:
    if request.endpoint == "static":
        return True
    agent = (request.user_agent.string or "").lower()
    return any(a in agent for a in _CRAWLER_AGENTS) and _is_verified_crawler_ip(get_remote_address())


limiter = Limiter(
    key_func=get_remote_address,
    # application_limits = one shared counter per IP across every route.
    # default_limits would instead give each route its own separate budget,
    # which isn't "one source hitting the site a lot" — it's easy to get
    # backwards, so don't swap this without re-testing across >1 route.
    application_limits=[f"{REQUESTS_PER_HOUR} per hour"],
    application_limits_exempt_when=_is_exempt_request,
    storage_uri="memory://",
)
