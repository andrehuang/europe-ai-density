#!/usr/bin/env python3
"""Fetch the CSRankings faculty roster and country map.

CSRankings lists full-time, tenure-track faculty who can independently supervise CS
doctoral students at a listed university. That admission rule is close enough to our
condition (a) that a CSRankings listing substitutes for individual title verification,
which is what keeps the adjudication budget finite.

Writes an immutable dated snapshot under data/raw/csrankings/<date>/ and a merged
extract at data/derived/csrankings_europe.csv.
"""

import csv
import io
import pathlib
import string
import sys
import urllib.request

BASE = "https://raw.githubusercontent.com/emeryberger/CSrankings/gh-pages"
ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT_DATE = "2026-08-06"

# EU-27 + EFTA + UK, as CSRankings country abbreviations.
IN_SCOPE = {
    "at", "be", "bg", "hr", "cy", "cz", "dk", "ee", "fi", "fr", "de", "gr", "hu",
    "ie", "it", "lv", "lt", "lu", "mt", "nl", "pl", "pt", "ro", "sk", "si", "es",
    "se",                                            # EU-27
    "ch", "no", "is", "li",                          # EFTA
    "gb", "uk",                                      # United Kingdom (CSRankings uses "gb")
}
# Deliberately out of scope though CSRankings files them under region=europe:
# tr (Turkey), il (Israel), ru (Russia), ua (Ukraine), rs/ba/mk (Western Balkans).
# These belong in the appendix table, never the main ranking.


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "europe-ai-density/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def main() -> int:
    raw_dir = ROOT / "data" / "raw" / "csrankings" / SNAPSHOT_DATE
    raw_dir.mkdir(parents=True, exist_ok=True)
    derived_dir = ROOT / "data" / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    # institutions.csv maps institution -> region, country abbreviation, department homepage.
    # The homepage column is the entry point for the later faculty-directory pass.
    inst_bytes = get(f"{BASE}/institutions.csv")
    (raw_dir / "institutions.csv").write_bytes(inst_bytes)
    country_of, homepage_of = {}, {}
    for row in csv.DictReader(io.StringIO(inst_bytes.decode("utf-8"))):
        country_of[row["institution"]] = row.get("countryabbrv", "")
        homepage_of[row["institution"]] = row.get("homepage", "")

    faculty = []
    for letter in string.ascii_lowercase:
        url = f"{BASE}/csrankings-{letter}.csv"
        try:
            data = get(url)
        except Exception as exc:  # a letter file may not exist
            print(f"  skip {letter}: {exc}", file=sys.stderr)
            continue
        (raw_dir / f"csrankings-{letter}.csv").write_bytes(data)
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        faculty.extend(rows)
        print(f"  {letter}: {len(rows)} rows")

    europe = []
    for row in faculty:
        aff = row.get("affiliation", "")
        country = country_of.get(aff, "")
        if country in IN_SCOPE:
            orcid = row.get("orcid", "")
            if orcid == "0000-0000-0000-0000":  # CSRankings' placeholder for "unknown"
                orcid = ""
            europe.append(
                {
                    "name": row.get("name", ""),
                    "affiliation": aff,
                    "country": country,
                    "homepage": row.get("homepage", ""),
                    "scholarid": row.get("scholarid", ""),
                    "orcid": orcid,
                }
            )

    fields = ["name", "affiliation", "country", "homepage", "scholarid", "orcid"]
    out = derived_dir / "csrankings_europe.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(europe, key=lambda r: (r["country"], r["affiliation"], r["name"])))

    counts: dict[tuple[str, str], int] = {}
    for r in europe:
        counts[(r["country"], r["affiliation"])] = counts.get((r["country"], r["affiliation"]), 0) + 1
    inst_out = derived_dir / "csrankings_europe_institutions.csv"
    with inst_out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["country", "affiliation", "csrankings_faculty", "dept_homepage"])
        for (country, aff), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            writer.writerow([country, aff, n, homepage_of.get(aff, "")])

    with_orcid = sum(1 for r in europe if r["orcid"])
    print(f"\nworldwide faculty rows : {len(faculty)}")
    print(f"in-scope faculty rows  : {len(europe)}")
    print(f"  ... with ORCID       : {with_orcid} ({100 * with_orcid // max(len(europe), 1)}%)")
    print(f"in-scope institutions  : {len(counts)}")
    print(f"wrote {out}")
    print(f"wrote {inst_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
