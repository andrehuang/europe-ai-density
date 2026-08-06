#!/usr/bin/env python3
"""First end-to-end pass: cluster geocoded institutions and compute density.

This exercises the whole chain — roster, geocoding, clustering, population grid — on the
CSRankings layer alone. It is a pipeline test, not a result: the T1 layer inherits every
CSRankings coverage gap documented in audit/00-source-coverage.md, so France, Spain and
Italy are badly under-counted and MPI-IS is missing entirely.

Cities are derived, not chosen: institutions within LINK_KM of each other are joined by
single linkage, and any cluster with at least MIN_PIS people enters the ranking.

Population is summed over the union of discs of CATCHMENT_KM around the cluster's
institutions, so the numerator and denominator describe the same ground.

Run with the project venv: .venv/bin/python scripts/build_ranking.py
"""

import csv
import pathlib
import sys
from collections import defaultdict

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"

LINK_KM = 10.0        # single-linkage threshold that defines a cluster
CATCHMENT_KM = 15.0   # radius around each institution for the population catchment
NEIGHBOUR_KM = 10.0   # radius for the "median neighbour count" measure
MIN_PIS = 5
# Activity threshold: papers at a core-layer venue inside the window. One paper over
# 5.6 years admits people whose AI work is incidental; three is roughly the output of a
# finishing doctorate, which is the floor for someone running an AI agenda. Kept as a
# parameter because it is a judgement call and the site exposes it as a toggle.
CORE_MIN = 3
EARTH_R = 6371.0088


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def main() -> int:
    insts = {}
    for r in csv.DictReader((DERIVED / "institutions_geocoded.csv").open(encoding="utf-8")):
        if r["lat"]:
            insts[(r["country"], r["name"])] = r

    people = defaultdict(list)
    unmapped = 0
    for r in csv.DictReader((DERIVED / "candidates_csrankings.csv").open(encoding="utf-8")):
        if int(r["core_papers"]) < CORE_MIN:
            continue
        key = (r["country"], r["affiliation"])
        if key in insts:
            people[key].append(r)
        else:
            unmapped += 1
    total = sum(len(v) for v in people.values())
    print(f"people with >= {CORE_MIN} core papers, placed: {total} (unmapped: {unmapped})")

    keys = [k for k in people if people[k]]
    lat = np.array([float(insts[k]["lat"]) for k in keys])
    lon = np.array([float(insts[k]["lon"]) for k in keys])
    counts = np.array([len(people[k]) for k in keys])

    # Single-linkage clustering via union-find over pairs closer than LINK_KM.
    parent = list(range(len(keys)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(len(keys)):
        d = haversine(lat[i], lon[i], lat, lon)
        for j in np.nonzero(d < LINK_KM)[0]:
            union(i, int(j))

    clusters = defaultdict(list)
    for i in range(len(keys)):
        clusters[find(i)].append(i)
    print(f"institutions: {len(keys)} -> clusters: {len(clusters)}")

    grid = np.load(DERIVED / "ghspop_30ss_europe.npz")
    glat, glon, gpop = grid["lat"], grid["lon"], grid["pop"]

    # Neighbour counts are computed across everyone in the dataset, not within clusters.
    # Counting inside a cluster would just re-measure cluster size, and it would hide the
    # fact that a researcher in Delft has colleagues in Rotterdam and Leiden.
    all_lat = np.repeat(lat, counts)
    all_lon = np.repeat(lon, counts)
    all_owner = np.repeat(np.arange(len(keys)), counts)
    neighbours = np.empty(len(all_lat), dtype=np.int32)
    for i in range(len(all_lat)):
        d = haversine(all_lat[i], all_lon[i], all_lat, all_lon)
        neighbours[i] = int((d < NEIGHBOUR_KM).sum()) - 1
    print(f"neighbour counts computed over {len(all_lat)} people")

    rows = []
    for members in clusters.values():
        n = int(counts[members].sum())
        if n < MIN_PIS:
            continue
        mlat, mlon = lat[members], lon[members]
        # Name the cluster after the institution contributing the most people.
        lead = members[int(np.argmax(counts[members]))]
        name = insts[keys[lead]]["ror_city"] or insts[keys[lead]]["name"]
        country = keys[lead][0]

        # Population over the union of discs, via a bounding-box prefilter.
        pad = CATCHMENT_KM / 111.0
        box = (
            (glat > mlat.min() - pad) & (glat < mlat.max() + pad)
            & (glon > mlon.min() - pad / np.cos(np.radians(mlat.mean())))
            & (glon < mlon.max() + pad / np.cos(np.radians(mlat.mean())))
        )
        cand_lat, cand_lon, cand_pop = glat[box], glon[box], gpop[box]
        inside = np.zeros(len(cand_pop), dtype=bool)
        for a, b in zip(mlat, mlon):
            inside |= haversine(a, b, cand_lat, cand_lon) < CATCHMENT_KM
        pop = float(cand_pop[inside].sum())

        mask = np.isin(all_owner, members)
        neigh = neighbours[mask]
        rows.append(
            {
                "cluster": name,
                "country": country,
                "people": n,
                "institutions": len(members),
                "population": pop,
                "per_100k": 1e5 * n / pop if pop else float("nan"),
                "median_neighbours": float(np.median(neigh)) if len(neigh) else 0.0,
                "members": "; ".join(keys[i][1] for i in sorted(members, key=lambda i: -counts[i])[:4]),
            }
        )

    rows.sort(key=lambda r: -r["people"])
    out = DERIVED / f"ranking_t1_preview_min{CORE_MIN}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nclusters with >= {MIN_PIS} people: {len(rows)}\n")
    print("TOP 20 BY COUNT")
    print(f"  {'cluster':22s} {'cc':3s} {'ppl':>4s} {'pop':>11s} {'/100k':>7s} {'nbrs':>5s}")
    for r in rows[:20]:
        print(f"  {r['cluster'][:22]:22s} {r['country']:3s} {r['people']:4d} "
              f"{r['population']:11,.0f} {r['per_100k']:7.2f} {r['median_neighbours']:5.0f}")

    print("\nTOP 20 BY DENSITY (per 100k), clusters with >= 15 people")
    dense = sorted([r for r in rows if r["people"] >= 15], key=lambda r: -r["per_100k"])
    for r in dense[:20]:
        print(f"  {r['cluster'][:22]:22s} {r['country']:3s} {r['people']:4d} "
              f"{r['population']:11,.0f} {r['per_100k']:7.2f} {r['median_neighbours']:5.0f}")

    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
