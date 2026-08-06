#!/usr/bin/env python3
"""Single-pass parse of the DBLP dump, producing both recall inputs at once.

Output 1 — publication evidence. For every paper at a venue in data/venue_dblp_keys.csv
within the activity window, one row per (author, paper). This settles condition (c) for
every candidate without a single API call.

Output 2 — a person index of every DBLP person record: pid, primary name, aliases, ORCID,
and any <note type="affiliation"> entries. The ORCID column is what makes the CSRankings
roster joinable to DBLP without name-matching heuristics, and the affiliation notes find
researchers at institutions CSRankings omits, which is where most of the European
research-institute population lives.

All outputs are gzipped CSV under data/derived/.
"""

import csv
import gzip
import pathlib
import sys
from collections import Counter, defaultdict

from lxml import etree

ROOT = pathlib.Path(__file__).resolve().parent.parent
DUMP = ROOT / "data" / "raw" / "dblp" / "2026-08-06" / "dblp.xml.gz"
DERIVED = ROOT / "data" / "derived"

WINDOW_START = 2021
WINDOW_END = 2026  # snapshot 2026-08-01; 2026 is only partially indexed

PUB_TAGS = {"article", "inproceedings", "incollection", "proceedings"}


def load_venue_map():
    """Return (prefix -> (abbrev, layer)), longest prefix first for matching."""
    rows = list(csv.DictReader((ROOT / "data" / "venue_dblp_keys.csv").open(encoding="utf-8")))
    return sorted(
        ((r["dblp_prefix"], r["venue_abbrev"], r["layer"]) for r in rows),
        key=lambda t: -len(t[0]),
    )


def match_venue(key, venue_map):
    for prefix, abbrev, layer in venue_map:
        if key.startswith(prefix):
            return abbrev, layer
    return None, None


def main() -> int:
    if not DUMP.exists():
        print(f"missing dump: {DUMP}", file=sys.stderr)
        return 1
    DERIVED.mkdir(parents=True, exist_ok=True)
    venue_map = load_venue_map()

    pubs_path = DERIVED / "dblp_venue_authorships.csv.gz"
    people_path = DERIVED / "dblp_persons.csv.gz"

    n_records = n_pub_rows = n_papers = n_person = n_aff = n_orcid = 0
    n_former = n_phd = 0
    per_venue = Counter()
    per_year = Counter()

    pubs_fh = gzip.open(pubs_path, "wt", newline="", encoding="utf-8")
    people_fh = gzip.open(people_path, "wt", newline="", encoding="utf-8")
    pubs = csv.writer(pubs_fh)
    people = csv.writer(people_fh)
    pubs.writerow(["pid", "author", "venue", "layer", "year", "paper_key", "is_findings"])
    people.writerow(
        [
            "pid", "primary_name", "aliases", "orcid",
            "affiliations_current", "affiliations_former", "affiliations_phd",
            "phd_year", "homepage",
        ]
    )

    with gzip.open(DUMP, "rb") as raw:
        # lxml resolves the SYSTEM "dblp.dtd" reference relative to the file object's
        # name, and dblp.dtd sits beside the dump, so no base_url is needed.
        #
        # The tag filter matters for correctness, not just speed: end events fire for
        # children before their parent, so clearing on every element would wipe <year>
        # and <author> before the enclosing record is ever read.
        context = etree.iterparse(
            raw,
            events=("end",),
            tag=("article", "inproceedings", "incollection", "proceedings", "www"),
            load_dtd=True,
            resolve_entities=True,
            huge_tree=True,
        )
        for _, elem in context:
            tag = elem.tag
            if tag in PUB_TAGS:
                key = elem.get("key", "")
                venue, layer = match_venue(key, venue_map)
                if venue:
                    year_el = elem.find("year")
                    try:
                        year = int(year_el.text) if year_el is not None else 0
                    except (TypeError, ValueError):
                        year = 0
                    if WINDOW_START <= year <= WINDOW_END:
                        book = elem.find("booktitle")
                        journal = elem.find("journal")
                        container = (book if book is not None else journal)
                        container_text = (container.text or "") if container is not None else ""
                        is_findings = "findings" in container_text.lower()
                        authors = elem.findall("author")
                        for a in authors:
                            pubs.writerow(
                                [
                                    a.get("pid", ""),
                                    (a.text or "").strip(),
                                    venue,
                                    layer,
                                    year,
                                    key,
                                    "1" if is_findings else "0",
                                ]
                            )
                            n_pub_rows += 1
                        if authors:
                            n_papers += 1
                            per_venue[venue] += 1
                            per_year[year] += 1
            elif tag == "www":
                key = elem.get("key", "")
                if key.startswith("homepages/"):
                    author_els = elem.findall("author")
                    names = [(a.text or "").strip() for a in author_els]
                    pid = next((a.get("pid") for a in author_els if a.get("pid")), "")
                    if not pid:
                        pid = key[len("homepages/"):]
                    # Affiliation notes carry a label that decides how much they are worth:
                    # unlabelled means current, "former" means the person has left, and
                    # "PhD <year>" marks the doctoral institution. Treating all three alike
                    # is what makes an undated affiliation sweep look like a roster of
                    # people who left a decade ago.
                    current, former, phd, phd_year = [], [], [], ""
                    for n in elem.findall("note"):
                        if n.get("type") != "affiliation":
                            continue
                        text = (n.text or "").strip()
                        if not text:
                            continue
                        label = (n.get("label") or "").strip()
                        if label == "former":
                            former.append(text)
                        elif label.startswith("PhD"):
                            phd.append(text)
                            year = label[3:].strip()
                            if year.isdigit() and year > phd_year:
                                phd_year = year
                        else:
                            current.append(text)
                    # ORCIDs live in <url> children, not in a typed note.
                    orcid, homepage = "", ""
                    for u in elem.findall("url"):
                        text = (u.text or "").strip()
                        if "orcid.org/" in text:
                            if not orcid:
                                orcid = text.rsplit("orcid.org/", 1)[1].strip("/")
                        elif not homepage:
                            homepage = text
                    people.writerow(
                        [
                            pid,
                            names[0] if names else "",
                            "|".join(names[1:]),
                            orcid,
                            "|".join(current),
                            "|".join(former),
                            "|".join(phd),
                            phd_year,
                            homepage,
                        ]
                    )
                    n_person += 1
                    n_aff += len(current)
                    n_former += len(former)
                    n_phd += len(phd)
                    if orcid:
                        n_orcid += 1

            n_records += 1
            if n_records % 500_000 == 0:
                print(
                    f"  {n_records // 1000}k records | "
                    f"{n_papers} papers | {n_person} affiliated persons",
                    flush=True,
                )

            # Release memory: clear this record and drop every already-processed sibling,
            # including the record types the tag filter never emits events for.
            elem.clear()
            parent = elem.getparent()
            if parent is not None:
                while elem.getprevious() is not None:
                    del parent[0]

    pubs_fh.close()
    people_fh.close()

    print(f"\nrecords scanned        : {n_records}")
    print(f"in-window venue papers : {n_papers}")
    print(f"authorship rows        : {n_pub_rows}")
    print(f"person records         : {n_person}")
    print(f"  ... with ORCID       : {n_orcid}")
    print(f"  ... current affiliations: {n_aff}")
    print(f"  ... former affiliations : {n_former}")
    print(f"  ... PhD institutions    : {n_phd}")
    print("\npapers per year:")
    for y in sorted(per_year):
        print(f"  {y}: {per_year[y]}")
    print("\ntop venues:")
    for v, n in per_venue.most_common(15):
        print(f"  {v:10s} {n}")
    print(f"\nwrote {pubs_path}")
    print(f"wrote {people_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
