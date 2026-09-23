"""Shared data/profiles/index.json writer — one manifest across all cubes, each
cube owning its own top-level key. Pipeline-only; access never reads this file."""
import json
import os
from datetime import datetime, timezone

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "profiles"))
INDEX_PATH = os.path.join(OUTPUT_DIR, "index.json")


def update_manifest(cube: str, tables: dict[str, int]) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest = {}
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    manifest[cube] = {"built_at": datetime.now(timezone.utc).isoformat(), "tables": tables}
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest[cube]
