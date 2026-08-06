#!/usr/bin/env python3
"""Upgrade institution coordinates from city centroid to campus precision.

ROR v2 returns only the geonames coordinates of an institution's *city*, which is why
every Tübingen institution landed on the same point about 1.5 km from the actual campus.
That is harmless for assigning a city and damaging for the 10 km neighbour measure, where
a 1.5 km error is 15% of the radius and flips borderline pairs.

Postcodes were considered and rejected as the primary key. Their precision varies by
country by two orders of magnitude — a Dutch or British postcode names a street segment,
a German one a neighbourhood, a French or Italian one a whole commune — so a
postcode-based pipeline would carry country-dependent accuracy into a cross-country
comparison, which is the same defect the denominator choice had.

The target is the right *campus*, not the right building: people move around a site, and
the population grid is 1 km regardless. Anything below ~100 m is wasted effort.

Queries run against Nominatim at one per second per its usage policy, and every result is
rejected unless it falls within GUARD_KM of the ROR city, so a query cannot silently
relocate an institution to another country.

Output: data/derived/institutions_geocoded_precise.csv
"""

import csv
import difflib
import json
import math
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
CACHE = ROOT / "data" / "raw" / "nominatim" / "2026-08-06"
OUT = DERIVED / "institutions_geocoded_precise.csv"

API = "https://nominatim.openstreetmap.org/search"
UA = "europe-ai-density/0.1 (academic research; contact via repository)"
GUARD_KM = 30.0
EARTH_R = 6371.0088


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90]


def fold(text):
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", stripped).strip()


# Words that appear in almost every institution name and so carry no evidence that two
# names refer to the same place.
STOPWORDS = {
    "university", "universite", "universitat", "universita", "universidad", "universiteit",
    "universitet", "universitetet", "uniwersytet", "univerzita", "egyetem", "panepistimio",
    "institute", "institut", "instituto", "istituto", "school", "schule", "hochschule",
    "college", "centre", "center", "centro", "zentrum", "research", "forschung", "recherche",
    "de", "of", "the", "and", "et", "und", "di", "der", "des", "fur", "for", "science",
    "sciences", "technology", "technologie", "tecnologia", "polytechnic", "national",
}


def name_agrees(wanted, candidate, extra_stop=()):
    """True when the two names share a distinctive token or one contains the other.

    The city name must be in extra_stop. It is the commonest false friend: "University
    of Zurich" and "PH Zürich" share only "zurich", and matching on that returned the
    teacher-training college. The distance check already guarantees the city, so the
    city name carries no evidence about which institution this is.
    """
    if not candidate:
        return False
    stop = STOPWORDS | set(extra_stop)
    w = {t for t in wanted.split() if len(t) > 2 and t not in stop}
    c = {t for t in candidate.split() if len(t) > 2 and t not in stop}
    if w & c:
        return True
    # Cognates defeat token equality across languages: "Technische" against "Technical",
    # "Universität" against "University". A shared six-character prefix catches those
    # without admitting unrelated words.
    if any(a[:6] == b[:6] for a in w for b in c if len(a) > 5 and len(b) > 5):
        return True
    if candidate and (candidate in wanted or wanted.startswith(candidate)):
        return True
    # Most European institutions are named "University of <city>", so once the generic
    # words and the city name are removed there is nothing distinctive left to compare.
    # Whole-string similarity handles that case: "university of tubingen" against
    # "universitat tubingen" scores high, while "university of zurich" against
    # "ph zurich" — a different institution in the same city — does not.
    return difflib.SequenceMatcher(None, wanted, candidate).ratio() >= 0.65


def query(q, limit=5):
    path = CACHE / f"{slug(q)}--{limit}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    params = urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "limit": limit, "addressdetails": 1}
    )
    req = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # Never cache an empty response. A genuine "no such place" and a throttled
            # request look identical here, and caching the second freezes a transient
            # failure permanently — 29% of a previous run's cache was empty, including
            # queries that return results perfectly well on retry.
            if data:
                path.write_text(json.dumps(data), encoding="utf-8")
            time.sleep(1.2)  # Nominatim policy: at most one request per second
            return data
        except Exception as exc:
            if attempt == 2:
                print(f"    nominatim failed for {q!r}: {exc}", file=sys.stderr)
                return []
            time.sleep(3 * (attempt + 1))
    return []


def precision_of(hit):
    a = hit.get("address", {})
    if a.get("house_number"):
        return "building"
    if a.get("road"):
        return "street"
    if a.get("suburb") or a.get("city_district") or a.get("postcode"):
        return "district"
    return "area"


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((DERIVED / "institutions_geocoded.csv").open(encoding="utf-8")))
    print(f"institutions: {len(rows)}")

    sites_path = ROOT / "data" / "institution_sites.csv"
    site_queries = {}
    if sites_path.exists():
        for s in csv.DictReader(sites_path.open(encoding="utf-8")):
            if s["geocode_query"]:
                site_queries.setdefault(s["inst_id"], s["geocode_query"])
    print(f"explicit site queries: {len(site_queries)}")

    # Pull every name variant ROR holds for each institution out of the cached responses,
    # so the agreement check can compare against local-language forms too.
    ror_aliases = {}
    ror_cache = ROOT / "data" / "raw" / "ror" / "2026-08-06"
    for path in ror_cache.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("items", []):
            org = item.get("organization") or {}
            rid = org.get("id", "").rsplit("/", 1)[-1]
            if rid:
                ror_aliases.setdefault(
                    rid, [n.get("value", "") for n in (org.get("names") or [])]
                )
    print(f"ROR name variants loaded for {len(ror_aliases)} organisations")

    out, stats = [], {"building": 0, "street": 0, "district": 0, "area": 0, "city_centroid": 0}
    for i, r in enumerate(rows, 1):
        city_lat = float(r["lat"]) if r["lat"] else None
        city_lon = float(r["lon"]) if r["lon"] else None
        # Over-specified queries fail: "Universität Tübingen Fachbereich Informatik,
        # Sand 13, Tübingen" returns nothing while the plain institution name resolves
        # to the building. Name plus city is the reliable form.
        # An explicit query from data/institution_sites.csv wins: multi-site institutions
        # need a named campus, and a generic query returns whichever site the geocoder
        # happens to rank first — KTH's Södertälje campus rather than Stockholm.
        candidates = [
            site_queries.get(r["inst_id"]),
            f"{r['name']}, {r['ror_city']}" if r["ror_city"] else None,
            f"{r['ror_name']}, {r['ror_city']}" if r["ror_name"] and r["ror_city"] else None,
            r["name"],
        ]
        explicit = site_queries.get(r["inst_id"])
        chosen = None
        for q in [c for c in candidates if c]:
            hits = query(q)
            if not hits:
                continue
            # ROR's alias list carries the local-language name. Without it the check
            # rejects correct answers: OpenStreetMap returns "Kungliga Tekniska
            # högskolan", which shares nothing with "KTH Royal Institute of Technology".
            wanted = " ".join(
                fold(x) for x in
                [r["name"], r["ror_name"], *ror_aliases.get(r["ror_id"], ())]
            )
            city_tokens = set(fold(r["ror_city"]).split()) | set(fold(r["city_expected"]).split())
            viable = []
            for hit in hits:
                lat, lon = float(hit["lat"]), float(hit["lon"])
                dist = haversine(lat, lon, city_lat, city_lon) if city_lat is not None else 0.0
                if dist > GUARD_KM:
                    continue  # too far from the known city to be the right place
                # Distance and country agreeing is not enough. Querying "University of
                # Zurich" returned ZHAW in Winterthur — a different institution, in the
                # right country, 20 km away. The returned name has to agree too.
                head = fold(hit.get("display_name", "").split(",")[0])
                # A query written by hand in data/institution_sites.csv names the campus
                # deliberately, so it outranks a generic name heuristic. Everything else
                # must clear a strict bar, because a confidently wrong precise coordinate
                # is worse than an honest city centroid: a loose rule put TU Munich at the
                # EU Business School and EPFL at a sports hall, while the fallback would
                # have been right to within a couple of kilometres.
                if q == explicit or name_agrees(wanted, head, city_tokens):
                    viable.append((dist, lat, lon, hit))
            if not viable:
                continue
            # Several campuses can match. Prefer the one nearest the institution's
            # registered city, which picks KTH's Stockholm campus over Södertälje and
            # ETH Zentrum over the Oerlikon annexe.
            dist, lat, lon, hit = min(viable, key=lambda t: t[0])
            chosen = (lat, lon, precision_of(hit), q, hit.get("display_name", "")[:90])
            break

        if chosen:
            lat, lon, prec, q, disp = chosen
            shift = haversine(lat, lon, city_lat, city_lon) if city_lat is not None else 0.0
        else:
            lat, lon, prec, q, disp, shift = city_lat, city_lon, "city_centroid", "", "", 0.0
        stats[prec] += 1
        out.append(
            {**r, "lat": lat, "lon": lon, "geocode_precision": prec,
             "geocode_query": q, "geocode_display": disp,
             "shift_from_city_km": f"{shift:.2f}"}
        )
        if i % 50 == 0:
            print(f"  {i}/{len(rows)}", flush=True)

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    print("\nprecision achieved:")
    for k, v in stats.items():
        print(f"  {k:14s} {v}")
    shifts = sorted(out, key=lambda r: -float(r["shift_from_city_km"]))
    print("\nlargest corrections against the city centroid:")
    for r in shifts[:12]:
        print(f"  {float(r['shift_from_city_km']):6.2f} km  {r['name'][:38]:40s} {r['geocode_precision']}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
