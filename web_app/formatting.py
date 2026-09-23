"""Display-only text formatting for the all-caps source data. Never applied to
stored data or used in search matching (which is already case-insensitive) —
only in templates, via the `proper` Jinja filter registered in web_app/__init__.py.
"""

_MINOR_WORDS = {"of", "and", "the", "for", "in", "on", "at", "to", "a", "an"}

# Extend as new ones show up while browsing real data.
_ACRONYMS = {
    "OPP", "TTC", "CAO", "CEO", "CFO", "COO", "CIO", "EMS", "IT", "HR", "GO",
    "YMCA", "YWCA", "OPG", "LCBO", "TDSB", "TVO", "GTA",
}


def proper_case(text: str | None) -> str | None:
    if not text:
        return text
    words = text.split(" ")
    out = []
    for i, word in enumerate(words):
        if word.upper() in _ACRONYMS:
            out.append(word.upper())
            continue
        cased = word.title()  # per-token, so O'BRIEN -> O'Brien and SMITH-JONES -> Smith-Jones
        if cased.startswith("Mc") and len(cased) > 2:
            cased = "Mc" + cased[2].upper() + cased[3:]
        if cased.lower() in _MINOR_WORDS and i != 0:
            cased = cased.lower()
        out.append(cased)
    return " ".join(out)
