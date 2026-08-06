#!/usr/bin/env python3
"""Join the CSRankings roster to DBLP and apply the core-AI publication filter.

This is the step that turns "9,727 European CS faculty" into "the subset who actually
publish core AI", which is the first number in this project that means anything.

Also emits the affiliation-note sweep: every DBLP person carrying an institutional
affiliation note, which is the recall path for research institutes CSRankings omits.

Outputs (all under data/derived/):
  candidates_csrankings.csv    CSRankings roster + DBLP pid + venue paper counts
  dblp_affiliation_persons.csv.gz  persons with affiliation notes, for institute recall
"""

import csv
import gzip
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"

csv.field_size_limit(10_000_000)


def main() -> int:
    roster = list(csv.DictReader((DERIVED / "csrankings_europe.csv").open(encoding="utf-8")))
    want_orcid = {r["orcid"]: r for r in roster if r["orcid"]}
    want_name = defaultdict(list)
    for r in roster:
        want_name[r["name"]].append(r)
    print(f"CSRankings roster: {len(roster)} rows, {len(want_orcid)} with ORCID")

    # Pass 1 over the person index: resolve pids, and keep everyone with an affiliation note.
    pid_by_orcid, pid_by_name = {}, {}
    # A CSRankings name maps to the full set of DBLP name forms for that person, so
    # publication counts can be summed across aliases.
    aliases_of = {}
    aff_rows = []
    n_persons = 0
    with gzip.open(DERIVED / "dblp_persons.csv.gz", "rt", encoding="utf-8") as fh:
        for p in csv.DictReader(fh):
            n_persons += 1
            pid, name, orcid = p["pid"], p["primary_name"], p["orcid"]
            all_names = [name] + [a for a in p["aliases"].split("|") if a]
            if orcid and orcid in want_orcid:
                pid_by_orcid[orcid] = pid
                aliases_of.setdefault(want_orcid[orcid]["name"], all_names)
            for n in all_names:
                if n in want_name:
                    pid_by_name.setdefault(n, pid)
                    aliases_of.setdefault(n, all_names)
            if p["affiliations_current"] or p["affiliations_former"] or p["affiliations_phd"]:
                aff_rows.append(p)
    print(f"DBLP persons scanned: {n_persons}, with affiliation notes: {len(aff_rows)}")

    # Pass 2 over authorships: per-author-name venue counts.
    #
    # DBLP carries pid attributes only on person records, not on the author elements of
    # publication records, so the join key is the canonical author name — which is exactly
    # what CSRankings uses, homonym suffixes ("Chang Liu 0087") included.
    #
    # Findings volumes are excluded from the core layer per data/venues.csv and counted as
    # extended instead.
    core = Counter()
    extended = Counter()
    venues = defaultdict(set)
    years = defaultdict(set)
    with gzip.open(DERIVED / "dblp_venue_authorships.csv.gz", "rt", encoding="utf-8") as fh:
        for a in csv.DictReader(fh):
            name = a["author"]
            if not name:
                continue
            if a["layer"] == "core" and a["is_findings"] == "0":
                core[name] += 1
            else:
                extended[name] += 1
            venues[name].add(a["venue"])
            years[name].add(a["year"])

    print(f"author names with any venue paper: {len(venues)}")

    def stats_for(names):
        """Sum across a person's primary name and aliases."""
        names = [n for n in names if n]
        c = sum(core.get(n, 0) for n in names)
        e = sum(extended.get(n, 0) for n in names)
        v = set().union(*(venues.get(n, set()) for n in names)) if names else set()
        y = set().union(*(years.get(n, set()) for n in names)) if names else set()
        return c, e, v, y

    out_rows = []
    matched_orcid = matched_name = unmatched = 0
    for r in roster:
        pid = ""
        how = ""
        if r["orcid"] and r["orcid"] in pid_by_orcid:
            pid, how = pid_by_orcid[r["orcid"]], "orcid"
            matched_orcid += 1
        elif r["name"] in pid_by_name:
            pid, how = pid_by_name[r["name"]], "name"
            matched_name += 1
        else:
            unmatched += 1
        c, e, v, y = stats_for(aliases_of.get(r["name"], [r["name"]]))
        out_rows.append(
            {
                "name": r["name"],
                "affiliation": r["affiliation"],
                "country": r["country"],
                "orcid": r["orcid"],
                "dblp_pid": pid,
                "matched_by": how,
                "core_papers": c,
                "extended_papers": e,
                "venues": ";".join(sorted(v)),
                "last_year": max(y) if y else "",
                "homepage": r["homepage"],
            }
        )

    fields = [
        "name", "affiliation", "country", "orcid", "dblp_pid", "matched_by",
        "core_papers", "extended_papers", "venues", "last_year", "homepage",
    ]
    out = DERIVED / "candidates_csrankings.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    aff_out = DERIVED / "dblp_affiliation_persons.csv.gz"
    n_kept = 0
    with gzip.open(aff_out, "wt", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "pid", "primary_name", "orcid", "affiliations_current",
                "affiliations_former", "affiliations_phd", "phd_year",
                "core_papers", "extended_papers", "venues", "last_year", "homepage",
            ]
        )
        for p in aff_rows:
            names = [p["primary_name"]] + [a for a in p["aliases"].split("|") if a]
            c, e, v, y = stats_for(names)
            if c or e:  # only people with venue activity are candidates
                n_kept += 1
                w.writerow(
                    [
                        p["pid"], p["primary_name"], p["orcid"], p["affiliations_current"],
                        p["affiliations_former"], p["affiliations_phd"], p["phd_year"],
                        c, e, ";".join(sorted(v)), max(y) if y else "", p["homepage"],
                    ]
                )
    print(f"affiliation-note candidates with venue activity: {n_kept}")

    core_active = [r for r in out_rows if r["core_papers"] > 0]
    any_active = [r for r in out_rows if r["core_papers"] or r["extended_papers"]]
    print("\n--- CSRankings roster after the core-AI filter ---")
    print(f"matched to DBLP by ORCID : {matched_orcid}")
    print(f"matched to DBLP by name  : {matched_name}")
    print(f"unmatched                : {unmatched}")
    print(f"\ncore-layer active (>=1 paper) : {len(core_active)} / {len(roster)}")
    print(f"any layer active              : {len(any_active)} / {len(roster)}")

    by_country = Counter(r["country"] for r in core_active)
    print("\ncore-active by country:")
    for c, n in by_country.most_common():
        print(f"  {c}: {n}")

    by_inst = Counter((r["country"], r["affiliation"]) for r in core_active)
    print("\ntop 30 institutions by core-active faculty:")
    for (c, a), n in by_inst.most_common(30):
        print(f"  {n:4d}  {c}  {a}")

    print(f"\nwrote {out}")
    print(f"wrote {aff_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
