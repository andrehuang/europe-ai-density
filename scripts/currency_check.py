#!/usr/bin/env python3
"""Check every counted person against dated affiliations from their recent papers.

The weakest point in the count is people resting on a single institution page. Seong Joon
Oh was counted in Tübingen because tuebingen.ai still lists him; he has moved to KAIST,
DBLP holds no affiliation note for him, and nothing in the pipeline could contradict a
stale page. 38% of counted people are in that position.

OpenAlex records an institution *per paper, with years*, which is the one kind of evidence
an out-of-date directory cannot fake. Papers from 2024 onward say where somebody actually
was, recently.

This is a triage, not a verdict: a mismatch means look, not remove. Cross-appointments,
lagging metadata and author-disambiguation errors all produce mismatches that are not moves.

Output: data/derived/currency_check.csv
"""

import csv
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from instnames import city_key, names_agree  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
CACHE = ROOT / "data" / "raw" / "openalex" / "2026-08-06"
OUT = DERIVED / "currency_check.csv"

API = "https://api.openalex.org"
MAILTO = "europe-ai-density@example.org"   # the polite pool wants a contact
SINCE_YEAR = 2024


def fold(text):
    d = unicodedata.normalize("NFKD", (text or "").lower())
    s = "".join(c for c in d if not unicodedata.combining(c))
    s = re.sub(r"\s+\d{4}$", "", s)
    return re.sub(r"[^a-z ]+", " ", s).strip()


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90]


def get(url, cache_key):
    path = CACHE / f"{cache_key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            path.unlink()
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{sep}mailto={MAILTO}",
                                 headers={"User-Agent": "europe-ai-density/0.1"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # Empty results are not cached: a throttled request is indistinguishable from
            # a genuine miss, and caching the second freezes a transient failure.
            if data and data.get("results") != []:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data), encoding="utf-8")
            time.sleep(0.12)
            return data
        except Exception as exc:
            if attempt == 2:
                print(f"    openalex failed: {exc}", file=sys.stderr)
                return {}
            time.sleep(2 * (attempt + 1))
    return {}


def find_author(name, orcid):
    """Resolve a person to an OpenAlex author, refusing a doubtful match."""
    if orcid:
        d = get(f"{API}/authors?filter=orcid:{urllib.parse.quote(orcid)}", f"orcid-{slug(orcid)}")
        hits = d.get("results") or []
        if hits:
            return hits[0], "orcid"
    d = get(f"{API}/authors?search={urllib.parse.quote(name)}&per-page=5", f"name-{slug(name)}")
    hits = d.get("results") or []
    want = fold(name)
    exact = [h for h in hits if fold(h.get("display_name", "")) == want]
    if len(exact) == 1:
        return exact[0], "name"
    if len(exact) > 1:
        return None, f"ambiguous({len(exact)})"
    return None, "no_match"


def recent_affiliations(author):
    """Institution names carrying a year at or after SINCE_YEAR."""
    out = []
    for aff in author.get("affiliations") or []:
        years = aff.get("years") or []
        if any(y >= SINCE_YEAR for y in years):
            inst = aff.get("institution") or {}
            out.append((inst.get("display_name", ""), inst.get("country_code", ""),
                        max(years)))
    return out


def main() -> int:
    payload = (ROOT / "site" / "payload.js").read_text(encoding="utf-8")
    data = json.loads(payload[len("window.DENSITY_DATA = "):-1])

    orcid_of = {}
    for r in csv.DictReader((DERIVED / "csrankings_europe.csv").open(encoding="utf-8")):
        if r["orcid"]:
            orcid_of[fold(r["name"])] = r["orcid"]

    # Match against the institutions we know sit in each city, not against the city name.
    # Comparing city strings failed the same way it has failed twice before: fold("München")
    # is "munchen" and OpenAlex writes "Technical University of Munich", so TUM read as
    # elsewhere. Institution identity survives translation where city names do not.
    city_insts = defaultdict(set)
    for r in csv.DictReader((DERIVED / "institutions_geocoded_precise.csv").open(encoding="utf-8")):
        if r["ror_city"]:
            for nm in (r["name"], r["ror_name"]):
                if nm:
                    city_insts[fold(r["ror_city"])].add(fold(nm))

    # Re-key on the collapsed form: the registry writes "Munich" and the counting config
    # writes "München", so the two never met and TUM read as elsewhere for Munich people.
    for k in list(city_insts):
        city_insts[city_key(k)] |= city_insts[k]

    def same_place(city, inst_name):
        """True when an OpenAlex institution is one we have registered in this city."""
        target = fold(inst_name)
        if not target:
            return False
        for known in city_insts.get(city_key(city), ()):
            # Generic words are excluded, or "Sogang University" matches a Tübingen
            # institution on "university" and a move to Korea reads as staying put.
            if names_agree(known, target):
                return True
        return city_key(city) in city_key(target)

    rows = []
    tally = defaultdict(int)
    people = [(city, p) for city, v in data["audited"].items() for p in v["people"]]
    print(f"counted people to check: {len(people)}")

    for i, (city, p) in enumerate(people, 1):
        author, how = find_author(p["n"], orcid_of.get(fold(p["n"]), ""))
        if not author:
            tally["unresolved"] += 1
            rows.append({"person": p["n"], "counted_city": city, "match": how,
                         "openalex_id": "", "recent_affiliations": "", "verdict": "no_data",
                         "papers": p["p"], "sources": ";".join(p["s"])})
            continue
        affs = recent_affiliations(author)
        names = " | ".join(f"{n} ({c}, {y})" for n, c, y in affs)
        # The most recent year is what settles it. "Any affiliation matches" cannot
        # detect a move while the old post is still inside the window: Seong Joon Oh
        # shows Tübingen in 2025 and a Korean university in 2026, and the lenient rule
        # called that confirmation.
        if not affs:
            verdict = "no_data"
        else:
            newest = max(y for _, _, y in affs)
            here_years = [y for n, _, y in affs if same_place(city, n)]
            if not here_years:
                verdict = "elsewhere"
            elif max(here_years) >= newest:
                verdict = "confirms"
            else:
                verdict = "moved_since"
        tally[verdict] += 1
        rows.append({"person": p["n"], "counted_city": city, "match": how,
                     "openalex_id": author.get("id", "").rsplit("/", 1)[-1],
                     "recent_affiliations": names, "verdict": verdict,
                     "papers": p["p"], "sources": ";".join(p["s"])})
        if i % 40 == 0:
            print(f"  {i}/{len(people)}", flush=True)

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nverdicts: {dict(tally)}")
    print(f"\npeople whose recent papers place them somewhere else "
          f"(triage list, not a removal list):")
    flagged = [r for r in rows if r["verdict"] == "elsewhere"]
    flagged.sort(key=lambda r: -int(r["papers"]))
    for r in flagged[:30]:
        solo = " [single source]" if len(set(r["sources"].split(";"))) == 1 else ""
        print(f"  {r['papers']:4d}  {r['person'][:26]:28s} counted {r['counted_city']:14s}"
              f"{solo}\n        {r['recent_affiliations'][:96]}")
    print(f"\n  ... {len(flagged)} flagged in total")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
