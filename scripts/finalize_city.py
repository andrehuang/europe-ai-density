#!/usr/bin/env python3
"""Assemble a city's verified roster, exclusion table and density figures.

Consumes the reconciliation output and the adjudication rulings, writes the two
primary artefacts, and computes density over the same geometry as the headcount.

Usage: .venv/bin/python scripts/finalize_city.py tuebingen
"""

import csv
import gzip
import pathlib
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from namematch import NameIndex  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
CATCHMENT_KM = 15.0
NEIGHBOUR_KM = 10.0
EARTH_R = 6371.0088

CITY_INSTS = {
    "tuebingen": (
        "de-mpi-is-tue", "de-ellis-inst-tue", "de-ellis-institute-tue",
        "de-tue-ai-center", "de-mpi-kyb", "de-hertie-ai",
        "University of Tübingen",
    ),
}


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin((p2 - p1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def main() -> int:
    city = sys.argv[1] if len(sys.argv) > 1 else "tuebingen"

    core = Counter()
    index = NameIndex()
    with gzip.open(DERIVED / "dblp_venue_authorships.csv.gz", "rt", encoding="utf-8") as fh:
        for a in csv.DictReader(fh):
            if not a["author"]:
                continue
            index.add(a["author"])
            if a["layer"] == "core" and a["is_findings"] == "0":
                core[a["author"]] += 1

    rulings = {
        r["name"]: r
        for r in csv.DictReader(
            (ROOT / "data" / f"adjudication_rulings_{city}.csv").open(encoding="utf-8")
        )
    }
    recon = list(csv.DictReader((DERIVED / f"reconcile_{city}.csv").open(encoding="utf-8")))

    # Where a person was seen, for the redundancy grade and the audit trail.
    seen = {}
    for r in csv.DictReader((DERIVED / "roster_checked.csv").open(encoding="utf-8")):
        if r["inst_id"] in CITY_INSTS[city]:
            seen.setdefault(r["dblp_name"] or r["name"], set()).add(r["inst_id"])
    for r in csv.DictReader((DERIVED / "candidates_csrankings.csv").open(encoding="utf-8")):
        if r["affiliation"] in CITY_INSTS[city]:
            resolved, _ = index.resolve(r["name"])
            seen.setdefault(resolved or r["name"], set()).add("csrankings")

    people, exclusions = [], []
    for r in recon:
        name = r["name"]
        ruling = rulings.get(name)
        status = r["status"]
        if ruling:
            status = "include" if ruling["ruling"] == "include" else "exclude"
        if status == "include":
            sources = sorted(seen.get(name, set())) or ["adjudication"]
            people.append(
                {
                    "person_id": name.lower().replace(" ", "-"),
                    "full_name": name,
                    "city": city,
                    "core_papers_window": core.get(name, 0),
                    "sources": ";".join(sources),
                    "source_count": len(sources),
                    "tier": (ruling or {}).get("tier") or ("T1" if "csrankings" in sources else "T2"),
                    "status": "verified",
                    "evidence": r["sources"] or "adjudication queue",
                }
            )
        elif status == "exclude":
            exclusions.append(
                {
                    "candidate_name": name,
                    "city_considered": city,
                    "core_papers_window": core.get(name, 0),
                    "reason_code": (ruling or {}).get("reason_code") or r["reason_code"],
                    "reason": (ruling or {}).get("reason") or r["reason"],
                    "counts_toward": (ruling or {}).get("city_if_elsewhere", ""),
                    "confidence": (ruling or {}).get("evidence_confidence", "mechanical"),
                }
            )

    for path, rows in (
        (ROOT / "data" / "people.csv", people),
        (ROOT / "data" / "exclusions.csv", exclusions),
    ):
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # Density over the same geometry as the headcount.
    insts = [
        r for r in csv.DictReader((DERIVED / "institutions_geocoded.csv").open(encoding="utf-8"))
        if r["inst_id"] in CITY_INSTS[city] or r["name"] in CITY_INSTS[city]
    ]
    lat = np.array([float(r["lat"]) for r in insts if r["lat"]])
    lon = np.array([float(r["lon"]) for r in insts if r["lon"]])
    grid = np.load(DERIVED / "ghspop_30ss_europe.npz")
    glat, glon, gpop = grid["lat"], grid["lon"], grid["pop"]
    pad = CATCHMENT_KM / 111.0
    box = ((glat > lat.min() - pad) & (glat < lat.max() + pad)
           & (glon > lon.min() - 2 * pad) & (glon < lon.max() + 2 * pad))
    inside = np.zeros(int(box.sum()), dtype=bool)
    for a, b in zip(lat, lon):
        inside |= haversine(a, b, glat[box], glon[box]) < CATCHMENT_KM
    pop = float(gpop[box][inside].sum())

    n = len(people)
    solo = sum(1 for p in people if p["source_count"] == 1)
    print(f"=== {city} ===")
    print(f"verified PIs                 : {n}")
    print(f"excluded, with a reason      : {len(exclusions)}")
    print(f"found by exactly one source  : {solo} ({100 * solo // n}%)")
    print(f"catchment population ({CATCHMENT_KM:.0f} km): {pop:,.0f}")
    print(f"density                      : {1e5 * n / pop:.2f} per 100k")
    print()
    print("exclusions by reason code:")
    for code, k in Counter(e["reason_code"] for e in exclusions).most_common():
        print(f"  {code or '(none)':6s} {k}")
    moved = [e for e in exclusions if e["counts_toward"]]
    print(f"\npeople who count toward another city ({len(moved)}):")
    for e in moved:
        print(f"  {e['candidate_name'][:26]:28s} -> {e['counts_toward']}")
    print(f"\nwrote data/people.csv ({n}) and data/exclusions.csv ({len(exclusions)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
