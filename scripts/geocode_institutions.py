#!/usr/bin/env python3
"""Resolve every in-scope institution to a ROR record with coordinates.

ROR gives an identifier, a canonical name, a city, and geonames coordinates, which is
everything the spatial clustering needs. Matching is done through ROR's affiliation
endpoint and then verified two ways: the country must agree with what we already know,
and where we hold a department homepage, its domain should appear in the ROR record.

Anything failing either check is written out as needs_review rather than silently
accepted — a mis-geocoded institution moves every one of its people to the wrong city.

Responses are cached under data/raw/ror/<date>/ so reruns cost nothing.
Output: data/derived/institutions_geocoded.csv
"""

import csv
import difflib
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
CACHE = ROOT / "data" / "raw" / "ror" / "2026-08-06"
OUT = DERIVED / "institutions_geocoded.csv"

API = "https://api.ror.org/organizations"
MIN_SCORE = 0.8


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def fold(text):
    """Lowercase and strip diacritics so 'Tübingen' and 'Tubingen' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def name_similarity(query, candidate):
    return difflib.SequenceMatcher(None, fold(query), fold(candidate)).ratio()


def query_ror(name):
    path = CACHE / f"{slug(name)}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    url = f"{API}?{urllib.parse.urlencode({'affiliation': name})}"
    req = urllib.request.Request(url, headers={"User-Agent": "europe-ai-density/0.1"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            path.write_text(json.dumps(data), encoding="utf-8")
            time.sleep(0.15)
            return data
        except Exception as exc:
            if attempt == 2:
                print(f"    ROR query failed for {name!r}: {exc}", file=sys.stderr)
                return {"items": []}
            time.sleep(2 * (attempt + 1))
    return {"items": []}


def display_name(org):
    names = org.get("names") or []
    for n in names:
        if "ror_display" in (n.get("types") or []):
            return n.get("value", "")
    return names[0].get("value", "") if names else ""


def pick(data, expect_country, homepage, query):
    """Best item: right country first, then a domain confirmation, then name similarity.

    Name similarity replaces ROR's own score as the tie-breaker because the score
    happily returns 0.91 for "Università di Siena" -> "University of Pisa", which is
    the same country and completely wrong.
    """
    items = data.get("items") or []
    host = ""
    m = re.search(r"https?://([^/]+)", homepage or "")
    if m:
        host = m.group(1).lower().replace("www.", "")

    best = None
    for it in items:
        org = it.get("organization") or {}
        locs = org.get("locations") or []
        geo = (locs[0].get("geonames_details") or {}) if locs else {}
        country = (geo.get("country_code") or "").lower()
        domain_hit = any(
            host and (host.endswith(d) or d.endswith(host))
            for d in (org.get("domains") or [])
        )
        sim = max(
            (name_similarity(query, n.get("value", "")) for n in (org.get("names") or [])),
            default=0.0,
        )
        rank = (country == expect_country, domain_hit, sim)
        if best is None or rank > best[0]:
            best = (rank, it, geo, country, domain_hit, it.get("score", 0.0), sim)
    return best


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)

    targets = []
    for r in csv.DictReader((DERIVED / "csrankings_europe_institutions.csv").open(encoding="utf-8")):
        targets.append(
            {
                "inst_id": f"{r['country']}-{slug(r['affiliation'])}",
                "source": "csrankings",
                "name": r["affiliation"],
                "country": r["country"],
                "city_expected": "",
                "homepage": r["dept_homepage"],
                "csrankings_faculty": r["csrankings_faculty"],
            }
        )
    for r in csv.DictReader((ROOT / "data" / "institutions_supplement.csv").open(encoding="utf-8")):
        targets.append(
            {
                "inst_id": r["inst_id"],
                "source": "supplement",
                "name": r["name_en"],
                "country": r["country"],
                "city_expected": r["city"],
                "homepage": "",
                "csrankings_faculty": "",
            }
        )
    print(f"institutions to resolve: {len(targets)}")

    overrides = {}
    for r in csv.DictReader(
        (ROOT / "data" / "institution_ror_overrides.csv").open(encoding="utf-8")
    ):
        overrides[(r["country"], r["source_name"])] = r

    rows = []
    auto = review = 0
    for i, t in enumerate(targets, 1):
        # CSRankings uses "gb"; ROR/geonames use the ISO code "GB" too, so no remap needed.
        expect = t["country"].lower()
        ov = overrides.get((t["country"], t["name"]), {})
        query = ov.get("ror_query") or t["name"]
        data = query_ror(query)
        best = pick(data, expect, t["homepage"], query)
        base = {
            **t,
            "ror_query": query,
            "coords_from": ov.get("coords_from", ""),
            "override_note": ov.get("note", ""),
        }
        if best is None:
            rows.append({**base, "ror_id": "", "ror_name": "", "ror_city": "", "lat": "",
                         "lon": "", "score": "", "similarity": "", "domain_match": "",
                         "city_note": "", "status": "no_match"})
            review += 1
        else:
            _, it, geo, country, domain_hit, score, sim = best
            org = it["organization"]
            ok = country == expect and (sim >= 0.75 or domain_hit)
            # The expected city is a hint written by hand and often in the local language
            # ("Torino" vs ROR's "Turin"), so a mismatch is reported, not enforced.
            ror_city = geo.get("name", "")
            city_note = ""
            if t["city_expected"] and fold(t["city_expected"])[:5] not in fold(ror_city):
                city_note = f"expected {t['city_expected']}, ROR says {ror_city}"
            status = "auto" if ok else "needs_review"
            auto += status == "auto"
            review += status == "needs_review"
            rows.append(
                {
                    **base,
                    "ror_id": org.get("id", "").rsplit("/", 1)[-1],
                    "ror_name": display_name(org),
                    "ror_city": ror_city,
                    "lat": geo.get("lat", ""),
                    "lon": geo.get("lng", ""),
                    "score": f"{score:.2f}",
                    "similarity": f"{sim:.2f}",
                    "domain_match": "1" if domain_hit else "0",
                    "city_note": city_note,
                    "status": status,
                }
            )
        if i % 50 == 0:
            print(f"  {i}/{len(targets)} resolved", flush=True)

    # Second pass: multi-site institutions whose ROR record points at the wrong campus
    # borrow coordinates from a named neighbour, so no coordinate is ever hand-entered.
    by_id = {r["inst_id"]: r for r in rows}
    for r in rows:
        ref = r.get("coords_from")
        if ref and ref in by_id and by_id[ref].get("lat"):
            src = by_id[ref]
            r["lat"], r["lon"], r["ror_city"] = src["lat"], src["lon"], src["ror_city"]
            r["city_note"] = (r["city_note"] + f"; coords borrowed from {ref}").strip("; ")
            # An anchored institution has trustworthy coordinates even when ROR holds no
            # usable record for it — young institutes and virtual centres mostly.
            if r["status"] != "auto":
                r["status"] = "anchored"
        elif ref:
            r["status"] = "needs_review"
            r["city_note"] = (r["city_note"] + f"; coords_from {ref} unresolved").strip("; ")

    fields = [
        "inst_id", "source", "name", "country", "city_expected", "homepage",
        "csrankings_faculty", "ror_query", "ror_id", "ror_name", "ror_city", "lat", "lon",
        "score", "similarity", "domain_match", "coords_from", "city_note",
        "override_note", "status",
    ]
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"\nauto-accepted : {auto}")
    print(f"needs review  : {review}")
    print("\nstill unresolved (add a row to data/institution_ror_overrides.csv):")
    for r in rows:
        if r["status"] != "auto":
            print(f"  {r['country']:3s} {r['name'][:40]:42s} -> {r['ror_name'][:32]:34s} "
                  f"{r['ror_city'][:14]:16s} sim={r['similarity']}")
    flagged = [r for r in rows if r["status"] == "auto" and r["city_note"]]
    print(f"\nauto-accepted but with a city note ({len(flagged)}):")
    for r in flagged[:30]:
        print(f"  {r['country']:3s} {r['name'][:36]:38s} {r['city_note'][:64]}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
