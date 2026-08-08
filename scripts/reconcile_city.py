#!/usr/bin/env python3
"""Reconcile the two recall modalities for one city and produce an adjudication queue.

Institution directories and publication records disagree in opposite directions, so the
difference between them is the project's real work list. This script classifies every
disagreement using evidence already on hand, and queues only what genuinely needs a
human or an agent to look at a web page.

Mechanical dispositions, in order of authority:
  - CSRankings files the person at another institution -> they work there (E08 or a
    cross-appointment), and CSRankings affiliations were shown to be current.
  - DBLP labels the Tübingen affiliation "former" -> they left (E08).
  - DBLP labels it as the PhD institution -> trained there, not a PI (E02/E01).
  - Otherwise -> queued.

Usage: python3 scripts/reconcile_city.py tuebingen
Output: data/derived/reconcile_<city>.csv
"""

import csv
import gzip
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from namematch import NameIndex  # noqa: E402
from config import cities, city_by_slug, CORE_MIN  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
CORE_MIN = 3



def main() -> int:
    slugs = [c["slug"] for c in cities().values()]
    if len(sys.argv) < 2 or sys.argv[1] not in slugs:
        print(f"usage: {sys.argv[0]} <{'|'.join(slugs)}>", file=sys.stderr)
        return 1
    city_name, raw = city_by_slug(sys.argv[1])
    city = sys.argv[1]
    cfg = {"pattern": re.compile(raw["dblp_pattern"], re.I),
           "inst_ids": raw["rosters"], "csrankings": raw["csrankings"],
           "sites": {k: v[1] for k, v in raw["site_filters"].items()}}

    index = NameIndex()
    core = Counter()
    # Seed from DBLP person records first so alias spellings collapse to one identity.
    with gzip.open(DERIVED / "dblp_persons.csv.gz", "rt", encoding="utf-8") as fh:
        for p in csv.DictReader(fh):
            aliases = [a for a in p["aliases"].split("|") if a]
            if aliases:
                index.add_person(p["primary_name"], aliases)
    with gzip.open(DERIVED / "dblp_venue_authorships.csv.gz", "rt", encoding="utf-8") as fh:
        for a in csv.DictReader(fh):
            if not a["author"]:
                continue
            index.add(a["author"], weak=True)
            if a["layer"] == "core" and a["is_findings"] == "0":
                core[a["author"]] += 1

    # Roster-driven: institution directory passes plus the CSRankings layer.
    roster = {}
    for r in csv.DictReader((DERIVED / "roster_checked.csv").open(encoding="utf-8")):
        if r["inst_id"] not in cfg["inst_ids"] or int(r["core_papers"]) < CORE_MIN:
            continue
        allowed = cfg.get("sites", {}).get(r["inst_id"])
        # A multi-site institution's two halves belong to different cities, so a person
        # recorded at the other campus must not leak into this one.
        if allowed is not None and r.get("site", "") not in allowed:
            continue
        if True:
            name = r["dblp_name"] or r["name"]
            roster.setdefault(name, []).append(r["inst_id"])
    csr_elsewhere = {}
    for r in csv.DictReader((DERIVED / "candidates_csrankings.csv").open(encoding="utf-8")):
        resolved, _ = index.resolve(r["name"])
        key = resolved or r["name"]
        if r["affiliation"] in cfg["csrankings"]:
            if int(r["core_papers"]) >= CORE_MIN:
                roster.setdefault(key, []).append("csrankings")
        else:
            csr_elsewhere[key] = f"{r['affiliation']} ({r['country']})"

    # Every person's current DBLP affiliation, regardless of city. The roster-side
    # check needs this: somebody listed here whose publication record places them
    # elsewhere has to be questioned, and their notes never mention this city at all.
    dblp_current = {}
    # Publication-driven: DBLP says their current affiliation is in this city.
    pub = {}
    with gzip.open(DERIVED / "dblp_affiliation_persons.csv.gz", "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if int(r["core_papers"]) < CORE_MIN:
                continue
            here_current = bool(cfg["pattern"].search(r["affiliations_current"]))
            here_former = bool(cfg["pattern"].search(r["affiliations_former"]))
            here_phd = bool(cfg["pattern"].search(r["affiliations_phd"]))
            if r["affiliations_current"]:
                dblp_current[r["primary_name"]] = r["affiliations_current"]
            if here_current or here_former or here_phd:
                pub[r["primary_name"]] = {
                    "current": here_current, "former": here_former, "phd": here_phd,
                    "phd_year": r["phd_year"],
                    "affiliations_current": r["affiliations_current"],
                }

    rows = []
    for name in sorted(set(roster) | set(pub), key=lambda n: -core.get(n, 0)):
        in_roster, p = name in roster, pub.get(name)
        in_pub_current = bool(p and p["current"])
        if in_roster:
            status, code, why = "include", "", "on an institution directory here"
            elsewhere_note = dblp_current.get(name, "")
            if not in_pub_current and elsewhere_note and not cfg["pattern"].search(elsewhere_note):
                # The reconciliation has to run in both directions. Rosters omit people
                # who are there, and they also keep people who have gone: Hilde Kuehne
                # is listed at Tübingen by CSRankings while DBLP files her at Bonn.
                # Trusting the roster whenever it says anything would have let that
                # through unexamined, which is the asymmetry this check removes.
                elsewhere = elsewhere_note.split("|")[0].split(",")[0].strip()
                status, code = "queue", ""
                why = f"on a local directory, but DBLP's current affiliation is {elsewhere}"
            elif not in_pub_current:
                why += "; no corroborating DBLP affiliation note"
        elif not p:
            continue
        elif name in csr_elsewhere:
            status, code = "exclude", "E08"
            why = f"CSRankings files them at {csr_elsewhere[name]}"
        elif p["former"] and not p["current"]:
            status, code, why = "exclude", "E08", "DBLP labels the affiliation former"
        elif p["phd"] and not p["current"]:
            status, code, why = "exclude", "E02", f"DBLP records this as the PhD institution ({p['phd_year']})"
        elif re.search(r"International Max Planck Research School|IMPRS", p["affiliations_current"], re.I):
            status, code = "exclude", "E02"
            why = "affiliation is the IMPRS doctoral school, not a faculty post"
        elif (
            len(p["affiliations_current"].split("|")) > 1
            and not cfg["pattern"].search(p["affiliations_current"].split("|")[0])
        ):
            # DBLP lists the primary affiliation first. Somebody whose primary post is
            # elsewhere and who appears on none of this city's directories is not a PI
            # here — and with several overlapping local sources, absence from all of
            # them carries weight.
            elsewhere = p["affiliations_current"].split("|")[0].split(",")[0].strip()
            status, code = "exclude", "E08"
            why = f"DBLP's primary current affiliation is {elsewhere}; on none of the local directories"
        else:
            status, code, why = "queue", "", "current DBLP affiliation here but on no institution directory"
        rows.append(
            {
                "name": name,
                "core_papers": core.get(name, 0),
                "sources": ";".join(roster.get(name, [])),
                "dblp_current": p["affiliations_current"][:120] if p else "",
                "status": status,
                "reason_code": code,
                "reason": why,
            }
        )

    out = DERIVED / f"reconcile_{city}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    tally = Counter(r["status"] for r in rows)
    print(f"{city}: {len(rows)} names across both modalities -> {dict(tally)}")
    print(f"\nmechanically excluded ({tally['exclude']}):")
    for r in rows:
        if r["status"] == "exclude":
            print(f"  {r['core_papers']:4d}  {r['name'][:30]:32s} {r['reason_code']}  {r['reason'][:56]}")
    print(f"\nQUEUED for adjudication ({tally['queue']}):")
    for r in rows:
        if r["status"] == "queue":
            print(f"  {r['core_papers']:4d}  {r['name'][:30]:32s} {r['dblp_current'][:60]}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
