"""Current-year salary distribution in fixed bands, for the employer, sector,
position and combo dashboards. Counts disclosed people by salary paid (the
figure that puts someone on the list), from top_earners_history — one row
per person per year.
"""
from __future__ import annotations

from functools import lru_cache

from access.db import query

# (lower bound, label); each band runs up to, not including, the next bound.
SALARY_BANDS = [
    (100_000, "$100K–150K"),
    (150_000, "$150K–200K"),
    (200_000, "$200K–300K"),
    (300_000, "$300K–500K"),
    (500_000, "$500K+"),
]


@lru_cache(maxsize=256)
def salary_distribution(year: int, employer_id: str | None = None, sector_id: str | None = None,
                        title_norm: str | None = None) -> list[dict]:
    """One row per band, empty bands included as 0, so every chart has the
    same five bars; pct_of_max is each band's bar height (largest band = 100)."""
    conditions = ["year = ?"]
    params: list = [year]
    if employer_id:
        conditions.append("employer_id = ?")
        params.append(employer_id)
    if sector_id:
        conditions.append("sector_id = ?")
        params.append(sector_id)
    if title_norm:
        conditions.append("title_norm = ?")
        params.append(title_norm)

    bounds = [b for b, _ in SALARY_BANDS]
    df = query(f"""
        SELECT CASE {' '.join(f'WHEN salary_paid >= {b} THEN {i}' for i, b in reversed(list(enumerate(bounds))))}
                    ELSE 0 END AS band,
               COUNT(*)::INTEGER AS n
        FROM top_earners_history
        WHERE {' AND '.join(conditions)}
        GROUP BY band
    """, params)
    counts = dict(zip(df["band"], df["n"]))
    max_n = max(counts.values(), default=0)
    return [
        {"label": label, "n": int(counts.get(i, 0)),
         "pct_of_max": round(counts.get(i, 0) / max_n * 100, 1) if max_n else 0}
        for i, (_, label) in enumerate(SALARY_BANDS)
    ]


if __name__ == "__main__":
    print(salary_distribution(2025))
    print(salary_distribution(2025, sector_id="8", title_norm="CONSTABLE"))
