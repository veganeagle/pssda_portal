"""Home-page visit counter: one running total of every home-page load,
persisted to data/visits.txt so it survives restarts. Stores nothing about
the visitor, only the count.

Same single-process assumption as rate_limit.py and export_limit.py — the
lock only serializes threads within one process.
"""
import os
from threading import Lock

COUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "visits.txt"))

_lock = Lock()


def record_visit() -> int:
    """Adds one visit and returns the new total."""
    with _lock:
        count = 1
        if os.path.exists(COUNT_PATH):
            with open(COUNT_PATH, "r", encoding="utf-8") as f:
                count = int(f.read()) + 1
        with open(COUNT_PATH, "w", encoding="utf-8") as f:
            f.write(str(count))
        return count
