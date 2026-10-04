"""Per-IP throttle on CSV exports of a full employer roster, counted in
profiles delivered (not requests, not lines) — the existing request-count
limiter in rate_limit.py doesn't know how many rows a response contains, so
this is a separate, small mechanism with the same philosophy: in-memory,
single-process, per-IP, resets on restart, doesn't coordinate across workers.

Why a separate limit at all: an employer-scoped search already shows
everything inline once it's ENTITY_FULL_THRESHOLD rows or fewer, and even a
paginated large employer is still fully *visible* a page at a time — this
only throttles the one action that can hand over a lot of data in a single
response, which is the actual shape of a scraping risk, not browsing.
"""
import time
from collections import defaultdict
from threading import Lock

EXPORT_PROFILES_PER_HOUR = 20_000  # clears the single largest employer (TDSB, ~14K) in one go

_WINDOW_SECONDS = 3600
_lock = Lock()
_usage: dict[str, list[tuple[float, int]]] = defaultdict(list)


def check_and_record_export(ip: str, count: int) -> bool:
    """Returns True and records `count` profiles against `ip`'s rolling-hour
    budget if there's room; returns False (and records nothing) if this
    export would push that IP over EXPORT_PROFILES_PER_HOUR."""
    now = time.monotonic()
    cutoff = now - _WINDOW_SECONDS
    with _lock:
        entries = [(t, c) for t, c in _usage[ip] if t > cutoff]
        used = sum(c for _, c in entries)
        if used + count > EXPORT_PROFILES_PER_HOUR:
            _usage[ip] = entries
            return False
        entries.append((now, count))
        _usage[ip] = entries
        return True
