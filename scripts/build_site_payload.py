#!/usr/bin/env python3
"""Build the self-contained data payload for the interactive site.

A published page cannot fetch anything, so the population grid has to travel inside it.
Two tiers keep that affordable: a 0.02 degree grid within ~65 km of an institution, which
is what radius queries actually read, and a 0.1 degree backdrop everywhere else, which
exists only so Europe is visible. The grid is the basemap — there are no map tiles, and
cities show up as bright cells on their own.

Arrays are base64-encoded typed arrays rather than JSON numbers, which is roughly four
times smaller.

Output: site/payload.js
"""

import base64
import csv
import gzip
import json
import pathlib
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from namematch import NameIndex, fold  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
OUT = ROOT / "site" / "payload.js"

CORE_MIN = 3
FINE_DEG = 0.02
COARSE_DEG = 0.1

# Cities taken through the full protocol, with the rosters that make them up.
AUDITED = {
    "Tübingen": {
        "rosters": ("de-mpi-is-tue", "de-ellis-inst-tue", "de-ellis-institute-tue",
                    "de-tue-ai-center", "de-mpi-kyb", "de-hertie-ai"),
        "csrankings": ("University of Tübingen",),
        "site_filter": {"de-mpi-is-tue": ("campus", ("Tübingen", "unclear"))},
    },
    "Saarbrücken": {
        "rosters": ("de-saarland-university", "de-cispa-helmholtz-center", "de-mpi-inf",
                    "de-dfki-sb", "de-mpi-sws"),
        "csrankings": ("Saarland University", "CISPA Helmholtz Center"),
        "site_filter": {"de-mpi-sws": ("site", ("Saarbrücken",)),
                        "de-dfki-sb": ("location", ("Saarbrücken",))},
    },
    "Stuttgart": {
        "rosters": ("de-university-of-stuttgart", "de-mpi-is-stu"),
        "csrankings": ("University of Stuttgart",),
        "site_filter": {"de-mpi-is-stu": ("campus", ("Stuttgart",))},
    },
    "München": {
        "rosters": ("de-tu-munich", "de-lmu-munich", "de-mcml"),
        "csrankings": ("TU Munich", "LMU Munich", "Bundeswehr University Munich"),
        # Garching is 12 km out and part of the same cluster; Heilbronn and Straubing
        # are 120 km away and are not.
        "site_filter": {"de-tu-munich": ("campus", ("Garching", "Munich city centre",
                                                    "Munich", "München", "unclear", ""))},
    },
    "Berlin": {
        "rosters": ("de-tu-berlin",),
        "csrankings": ("TU Berlin", "Humboldt University of Berlin", "Freie Universitaet Berlin"),
        "site_filter": {},
    },
    "Kaiserslautern": {
        "rosters": ("de-mpi-sws",),
        "csrankings": ("TU Kaiserslautern",),
        "site_filter": {"de-mpi-sws": ("site", ("Kaiserslautern",))},
    },
}


def same_city(a, b):
    """Compare city names across German transliteration: Tübingen == Tuebingen."""
    def norm(x):
        x = fold(x)
        for pair in (("ue", "u"), ("oe", "o"), ("ae", "a"), ("ss", "s")):
            x = x.replace(*pair)
        return x
    return norm(a) == norm(b)


def slugify(city):
    return (city.lower().replace("ü", "ue").replace("ö", "oe").replace("ä", "ae")
            .replace("ß", "ss").replace(" ", "-"))


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode("ascii")


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)

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
            index.add(a["author"])
            if a["layer"] == "core" and a["is_findings"] == "0":
                core[a["author"]] += 1

    insts = {}
    for r in csv.DictReader((DERIVED / "institutions_geocoded_precise.csv").open(encoding="utf-8")):
        if r["lat"]:
            insts[r["name"]] = r
            insts[r["inst_id"]] = r

    # The title ruling, which until now was computed and never applied. data/titles.csv
    # exists so the PI judgement happens once, in one auditable place — but the counting
    # path took anyone on a roster who cleared the publication filter, whatever their
    # title. Postdocs and doctoral students on a directory page were being counted.
    verdicts = {}
    tp = DERIVED / "roster_titled.csv"
    if tp.exists():
        for r in csv.DictReader(tp.open(encoding="utf-8")):
            verdicts[(r["inst_id"], r["name"])] = r["verdict"]

    # --- audited people, one entry each, with the sources that found them -------------
    audited = defaultdict(dict)
    for city, cfg in AUDITED.items():
        for inst_id in cfg["rosters"]:
            path = ROOT / "data" / "raw" / "directories" / "2026-08-06" / inst_id / "roster.csv"
            if not path.exists():
                continue
            col, allowed = cfg["site_filter"].get(inst_id, (None, None))
            for r in csv.DictReader(path.open(encoding="utf-8")):
                if col and r.get(col, "") not in allowed:
                    continue
                # An unruled title is held out rather than assumed to qualify: it stays
                # visible in data/derived/roster_titled.csv as a review item.
                if verdicts.get((inst_id, r["name"]), "unknown") != "include":
                    continue
                name, _ = index.resolve(r["name"])
                key = name or fold(r["name"])
                entry = audited[city].setdefault(
                    key, {"n": name or r["name"], "p": core.get(name, 0) if name else 0, "s": []}
                )
                entry["s"].append(inst_id)
        for aff in cfg["csrankings"]:
            for r in csv.DictReader((DERIVED / "candidates_csrankings.csv").open(encoding="utf-8")):
                if r["affiliation"] != aff or int(r["core_papers"]) < CORE_MIN:
                    continue
                name, _ = index.resolve(r["name"])
                key = name or fold(r["name"])
                entry = audited[city].setdefault(
                    key, {"n": name or r["name"], "p": int(r["core_papers"]), "s": []}
                )
                entry["s"].append("csrankings")

    # Adjudication outcomes override the rosters: a city that has been reconciled has
    # people the directories missed and exclusions the directories wrongly included.
    rulings = {}
    rulings_path = ROOT / "data" / "adjudication_rulings_tuebingen.csv"
    if rulings_path.exists():
        for r in csv.DictReader(rulings_path.open(encoding="utf-8")):
            name, _ = index.resolve(r["name"])
            rulings[name or fold(r["name"])] = r
    backfill = ROOT / "data" / "raw" / "adjudication" / "2026-08-06" / "stuttgart" / "backfill.csv"
    if backfill.exists():
        for r in csv.DictReader(backfill.open(encoding="utf-8")):
            if "Stuttgart" not in r["current_city"] or r["leads_own_group"] != "yes":
                continue
            name, _ = index.resolve(r["name"])
            key = name or fold(r["name"])
            audited["Stuttgart"].setdefault(
                key, {"n": name or r["name"], "p": core.get(name, 0) if name else 0,
                      "s": ["adjudication"]}
            )

    # Cross-appointments established by adjudication. Only these can drive the
    # attribution switch: a roster's free-text "other affiliations" column names
    # institutions, not cities, and guessing the city from it would put made-up
    # precision behind a control that changes the ranking.
    primary_city = {}
    for city in AUDITED:
        rp = ROOT / "data" / f"adjudication_rulings_{slugify(city)}.csv"
        if rp.exists():
            for r in csv.DictReader(rp.open(encoding="utf-8")):
                if (r["ruling"] == "include" and r.get("city_if_elsewhere")
                        and not same_city(r["city_if_elsewhere"], city)):
                    name, _ = index.resolve(r["name"])
                    primary_city[name or fold(r["name"])] = r["city_if_elsewhere"]
        cp = (ROOT / "data" / "raw" / "adjudication" / "2026-08-06"
              / slugify(city) / "conflicts.csv")
        if cp.exists():
            for r in csv.DictReader(cp.open(encoding="utf-8")):
                pc = (r.get("primary_city") or "").strip()
                if pc and not same_city(pc, city):
                    name, _ = index.resolve(r["name"])
                    primary_city[name or fold(r["name"])] = pc

    reconciled = {"Tübingen"}
    audited_out = {}
    for city, people in audited.items():
        for key, r in rulings.items():
            if city != "Tübingen":
                continue
            if r["ruling"] == "exclude":
                people.pop(key, None)
            elif key not in people:
                people[key] = {"n": r["name"], "p": core.get(key, 0), "s": ["adjudication"]}
        for v in people.values():
            # Tier follows provenance, as defined in the README: a university faculty
            # roster is T1, a research-institute roster T2, and anyone recovered only by
            # the reconciliation is T3 — the layer that must be applied to every city or
            # to none.
            srcs = set(v["s"])
            v["t"] = ("T1" if "csrankings" in srcs
                      else "T3" if srcs == {"adjudication"}
                      else "T2")
        for key, v in people.items():
            pc = primary_city.get(key)
            if pc:
                v["pc"] = pc      # primary city, when it is not this one
                v["nc"] = 2       # cities this person is counted in
        kept = [v for v in people.values() if v["p"] >= CORE_MIN]
        kept.sort(key=lambda v: -v["p"])
        ref = insts.get(city) or next(
            (insts[i] for i in AUDITED[city]["rosters"] if i in insts), None
        )
        audited_out[city] = {
            "people": kept,
            "lat": float(ref["lat"]) if ref else None,
            "lon": float(ref["lon"]) if ref else None,
            # "reconciled" means both recall modalities were run and every disagreement
            # has a disposition. "roster-merged" means the directories are merged and
            # deduplicated but the publication-side reconciliation is still outstanding.
            "status": "reconciled" if city in reconciled else "roster-merged",
        }

    # --- preview layer: CSRankings only, every institution ---------------------------
    preview = defaultdict(list)
    seen_preview = defaultdict(set)
    for r in csv.DictReader((DERIVED / "candidates_csrankings.csv").open(encoding="utf-8")):
        if int(r["core_papers"]) < CORE_MIN:
            continue
        name, _ = index.resolve(r["name"])
        key = name or fold(r["name"])
        if key in seen_preview[r["affiliation"]]:
            continue  # CSRankings carries alias duplicates of the same person
        seen_preview[r["affiliation"]].add(key)
        preview[r["affiliation"]].append((name or r["name"], int(r["core_papers"])))

    points = []
    for name, papers in preview.items():
        inst = insts.get(name)
        if not inst:
            continue
        points.append({
            "n": name, "c": inst["country"], "city": inst["ror_city"],
            "lat": round(float(inst["lat"]), 4), "lon": round(float(inst["lon"]), 4),
            "k": len(papers),
            "pp": [[n, k] for n, k in sorted(papers, key=lambda t: -t[1])],
            "prec": inst["geocode_precision"],
        })
    points.sort(key=lambda p: -p["k"])

    # --- population grid, two tiers --------------------------------------------------
    g = np.load(DERIVED / "ghspop_30ss_europe.npz")
    lat, lon, pop = g["lat"], g["lon"], g["pop"]
    box = (lat > 34) & (lat < 72) & (lon > -25) & (lon < 32)
    lat, lon, pop = lat[box], lon[box], pop[box]

    ilat = np.array([p["lat"] for p in points])
    ilon = np.array([p["lon"] for p in points])
    near = np.zeros(len(pop), dtype=bool)
    for a, b in zip(ilat, ilon):
        near |= (np.abs(lat - a) < 0.6) & (np.abs(lon - b) < 0.9)

    def aggregate(mask, step, floor):
        la = np.round(lat[mask] / step).astype(np.int64)
        lo = np.round(lon[mask] / step).astype(np.int64)
        keys, inv = np.unique(la * 100000 + lo, return_inverse=True)
        agg = np.bincount(inv, weights=pop[mask])
        keep = agg > floor
        return (
            (keys[keep] // 100000).astype(np.int16),
            (keys[keep] % 100000).astype(np.int16),
            agg[keep].astype(np.float32),
        )

    fla, flo, fpop = aggregate(near, FINE_DEG, 20)
    cla, clo, cpop = aggregate(~near, COARSE_DEG, 500)
    print(f"fine cells {len(fpop)}, coarse cells {len(cpop)}")

    payload = {
        "meta": {
            "snapshot": "2026-08-01",
            "window": "2021-01-01 to 2026-08-01",
            "core_min": CORE_MIN,
            "fine_deg": FINE_DEG,
            "coarse_deg": COARSE_DEG,
            "grid_source": "GHS-POP R2023A epoch 2025, 30 arc-second",
        },
        "audited": audited_out,
        "institutions": points,
        "grid": {
            "fine": {"lat": b64(fla), "lon": b64(flo), "pop": b64(fpop)},
            "coarse": {"lat": b64(cla), "lon": b64(clo), "pop": b64(cpop)},
        },
    }

    OUT.write_text("window.DENSITY_DATA = " + json.dumps(payload, ensure_ascii=False) + ";",
                   encoding="utf-8")
    size = OUT.stat().st_size / 1e6
    print(f"audited cities: {[(c, len(v['people'])) for c, v in audited_out.items()]}")
    print(f"preview institutions: {len(points)}, people: {sum(p['k'] for p in points)}")
    print(f"wrote {OUT} ({size:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
