#!/usr/bin/env python3
"""Queue roster rows whose DBLP identity the matcher could not settle.

Two failure shapes, both of which used to be invisible:

- The name is ambiguous among DBLP homonyms and the affiliation tie-break did not
  decide it. "Frank Neumann" is one of five; only a person can say which.
- The name resolved confidently to a sparse DBLP record while a richer record of a
  longer name form exists. DBLP holds a bare "Björn Schuller" with no papers and no
  affiliation alongside "Björn W. Schuller" with sixty-two, and the roster says the
  short form. The affiliation tie-break cannot help here, because Schuller's DBLP
  affiliations name Imperial and Augsburg rather than Munich.

Before the matcher seeded every person record, these rows resolved by whichever
spelling the authorship stream reached first. That was not correct, it was lucky, and
where the luck ran out a person vanished from the count with no trace — Matthias Hein,
33 core papers, was in neither the count nor the exclusions.

Output: data/derived/identity_queue.csv, one row per unsettled roster row.
"""

import csv
import gzip
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from namematch import seeded_index  # noqa: E402
from config import cities, DERIVED, CORE_MIN  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    index, aff = seeded_index(DERIVED / "dblp_persons.csv.gz")
    core = {}
    with gzip.open(DERIVED / "dblp_venue_authorships.csv.gz", "rt", encoding="utf-8") as fh:
        for a in csv.DictReader(fh):
            if a["author"] and a["layer"] == "core" and a["is_findings"] == "0":
                core[a["author"]] = core.get(a["author"], 0) + 1

    inst_city = {i: c for c, cfg in cities().items() for i in cfg["rosters"]}

    out = []
    for r in csv.DictReader((DERIVED / "roster_checked.csv").open(encoding="utf-8")):
        city = inst_city.get(r["inst_id"])
        if not city:
            continue  # preview institutions are not counted; do not queue them
        got = int(r["core_papers"] or 0)
        # Only rows where a decision would change the count are worth a person's time.
        best = max((core.get(c, 0) for c in index.candidates(r["name"])), default=0)
        if got >= CORE_MIN or best < CORE_MIN:
            continue
        cands = sorted(index.candidates(r["name"]),
                       key=lambda c: -core.get(c, 0))[:6]
        out.append({
            "name": r["name"], "inst_id": r["inst_id"], "city": city,
            "matched_to": r["dblp_name"], "match": r["match"],
            "matched_papers": got, "best_candidate_papers": best,
            "candidates": " | ".join(
                f"{c} ({core.get(c, 0)}p; {aff.get(c, 'no affiliation')[:60]})"
                for c in cands),
            "title_verbatim": r.get("title_verbatim", ""),
            "evidence_url": r.get("evidence_url", ""),
        })

    out.sort(key=lambda r: -r["best_candidate_papers"])
    path = DERIVED / "identity_queue.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} unsettled identities affecting the count")
    for r in out[:30]:
        print(f"  {r['best_candidate_papers']:4d}p  {r['name'][:26]:28s} "
              f"{r['city']:14s} {r['match']}")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
