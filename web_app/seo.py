"""Search-engine indexing policy, in one place.

Indexable: the home page, the four tab landing pages, sector dashboards,
employer profiles, and the supporting text pages — and only in their plain
form (no filter/search query string; `back` is a navigation hint, not
content). Everything else — individual employee profiles, position and
employer+position pages, comparisons, filtered/search-result views — is
served with an X-Robots-Tag: noindex header.

Deliberately NOT done via robots.txt Disallow: a disallowed URL is never
fetched, so its noindex is never seen, and it can still be indexed from
external links. robots.txt only keeps crawlers off the CSV export.
"""
from flask import request

INDEXABLE_ENDPOINTS = {
    "home.index",
    "position.search", "employer.search", "employee.search", "top_earners.index",
    "sector.profile_page", "employer.profile_page",
    "pages.about", "pages.about_the_data", "pages.data_dictionary", "pages.contact", "pages.privacy", "pages.terms",
}

_IGNORED_ARGS = {"back"}


def is_indexable() -> bool:
    return request.endpoint in INDEXABLE_ENDPOINTS and not (set(request.args) - _IGNORED_ARGS)
