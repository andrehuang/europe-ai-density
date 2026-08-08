#!/usr/bin/env python3
"""Shared vocabulary for comparing institution and city names.

These words appear in almost every institution name, so sharing one is not evidence that
two names refer to the same place. The list lived inside the geocoder, was not reused,
and "Sogang University" then matched a Tübingen institution on the token "university" —
which made a researcher who had moved to Korea read as still in Tübingen.
"""

import re
import unicodedata

GENERIC = {
    "university", "universite", "universitat", "universita", "universidad", "universiteit",
    "universitet", "universitetet", "uniwersytet", "univerzita", "egyetem", "panepistimio",
    "institute", "institut", "instituto", "istituto", "school", "schule", "hochschule",
    "college", "centre", "center", "centro", "zentrum", "research", "forschung", "recherche",
    "science", "sciences", "technology", "technologie", "tecnologia", "polytechnic",
    "national", "federal", "state", "applied", "advanced", "studies", "laboratory",
    "department", "faculty", "group", "groups",
}

# German and English exonyms that must collapse to one key.
CITY_ALIASES = {
    "muenchen": "munich", "munchen": "munich", "koln": "cologne", "koeln": "cologne",
    "wien": "vienna", "praha": "prague", "warszawa": "warsaw", "lisboa": "lisbon",
    "roma": "rome", "milano": "milan", "torino": "turin", "napoli": "naples",
    "firenze": "florence", "venezia": "venice", "genova": "genoa", "athina": "athens",
    "gent": "ghent", "antwerpen": "antwerp", "bruxelles": "brussels", "brussel": "brussels",
    "geneve": "geneva", "zuerich": "zurich", "kobenhavn": "copenhagen",
}


def fold(text):
    d = unicodedata.normalize("NFKD", (text or "").lower())
    s = "".join(c for c in d if not unicodedata.combining(c))
    s = re.sub(r"\s+\d{4}$", "", s)
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def city_key(name):
    """Collapse transliteration and exonyms so Munchen, Muenchen and Munich agree."""
    x = fold(name)
    for a, b in (("ue", "u"), ("oe", "o"), ("ae", "a")):
        x = x.replace(a, b)
    return CITY_ALIASES.get(x, x)


def distinctive(name):
    """Tokens that actually identify an institution."""
    return {t for t in fold(name).split() if len(t) > 3 and t not in GENERIC}


def names_agree(a, b):
    """True when two institution names share something that identifies them."""
    da, db = distinctive(a), distinctive(b)
    if da & db:
        return True
    fa, fb = fold(a), fold(b)
    return bool(fa and fb and (fa in fb or fb in fa))
