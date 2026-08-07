#!/usr/bin/env python3
"""Apply the country-by-country title rules to every scraped directory roster.

The directory agents deliberately do not judge eligibility — they record the title
verbatim. The ruling happens here, once, against data/titles.csv, so the inclusion
rule lives in one auditable place and does not drift with whichever model did the
scraping.

Titles that data/titles.csv does not cover are reported rather than guessed. Each one
is a decision the project owes an explicit answer to.

Output: data/derived/roster_titled.csv
"""

import csv
import pathlib
import re
import sys
import unicodedata
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIRS = ROOT / "data" / "raw" / "directories"
OUT = ROOT / "data" / "derived" / "roster_titled.csv"


# German and French titles stack degrees, disciplines and honorifics around the rank
# word: "Prof. Dr. rer. nat. habil.", "Prof. Dr.-Ing.", "Prof. Dr. sc. ETH Zürich".
# Matching the whole string fails on all of them, so the decorations come off first and
# only the rank word is compared. 739 of 939 roster rows went unmatched without this.
DECORATION = re.compile(
    r"\b(?:"
    r"dr|drs|doktor|rer|nat|pol|oec|phil|med|jur|habil|ing|sc|scient|techn|"
    r"phd|ph|mult|hc|h\.?c|eth|zurich|zuerich|univ|mag|dipl|msc|bsc|"
    r"em|emerit\w*|i\.?r"
    r")\b\.?"
)


def normalise_title(text):
    """Reduce a decorated title to its rank word, keeping any qualifier in brackets."""
    t = fold(text)
    # A trailing role after a comma is a separate fact: "Prof. Dr., Core PI".
    t = t.split(",")[0]
    t = DECORATION.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def fold(text):
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", stripped).strip()


def load_rules():
    """country -> list of (folded title, counts_as_pi, tier, raw title)."""
    rules = defaultdict(list)
    for r in csv.DictReader((ROOT / "data" / "titles.csv").open(encoding="utf-8")):
        key = r["country"].upper()
        rules[key].append(
            (fold(r["title_local"]), r["counts_as_pi"], r["default_tier"], r["title_local"])
        )
        # The English gloss is also matchable: institute pages are often in English
        # even in non-anglophone countries.
        if r["title_en"]:
            rules[key].append(
                (fold(r["title_en"]), r["counts_as_pi"], r["default_tier"], r["title_local"])
            )
    return rules


def rule_for(title, country, rules):
    """Longest matching rule wins, so 'Assistant Professor' beats 'Professor'."""
    t = fold(title)
    if not t:
        return None
    # Country-specific rules are tried first; "XX" holds generic English titles that
    # institute pages use everywhere, and "EU" holds cross-cutting cases.
    for pool in (rules.get(country.upper(), []), rules.get("XX", []), rules.get("EU", [])):
        exact = [r for r in pool if r[0] == t]
        if exact:
            return max(exact, key=lambda r: len(r[0]))
        # A rule contained in the title means the title is the more specific string
        # ("Universitätsprofessor (W3)" contains "Universitätsprofessor"), which is a
        # safer read than the reverse.
        contained = [r for r in pool if r[0] and r[0] in t]
        if contained:
            return max(contained, key=lambda r: len(r[0]))
        looser = [r for r in pool if r[0] and t in r[0]]
        if looser:
            return min(looser, key=lambda r: len(r[0]))
    return None


def main() -> int:
    rules = load_rules()
    rosters = sorted(DIRS.glob("*/*/roster.csv"))
    if not rosters:
        print(f"no rosters under {DIRS}", file=sys.stderr)
        return 1

    out_rows = []
    unknown = Counter()
    per_inst = {}
    for path in rosters:
        inst_id = path.parent.name
        country = inst_id.split("-", 1)[0]
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        kept = dropped = unmatched = 0
        for r in rows:
            title = r.get("title_verbatim", "")
            hit = rule_for(title, country, rules)
            if hit is None:
                hit = rule_for(normalise_title(title), country, rules)
            if hit is None:
                verdict, tier, matched = "unknown", "", ""
                unknown[(country, title)] += 1
                unmatched += 1
            else:
                _, is_pi, tier, matched = hit
                verdict = "include" if is_pi == "yes" else "exclude"
                kept += verdict == "include"
                dropped += verdict == "exclude"
            out_rows.append(
                {
                    "inst_id": inst_id,
                    "country": country,
                    "name": r.get("name", ""),
                    "title_verbatim": title,
                    "matched_rule": matched,
                    "verdict": verdict,
                    "tier": tier,
                    "group_or_dept": r.get("group_or_dept") or r.get("team", ""),
                    "other_affiliations": (
                        r.get("other_affiliations")
                        or r.get("primary_affiliation")
                        or r.get("employer")
                        or r.get("campus", "")
                    ),
                    "personal_url": r.get("personal_url", ""),
                    "evidence_url": r.get("evidence_url", ""),
                    "notes": r.get("notes", ""),
                }
            )
        per_inst[inst_id] = (len(rows), kept, dropped, unmatched)

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    print(f"{'institution':28s} {'rows':>5s} {'incl':>5s} {'excl':>5s} {'?':>4s}")
    for inst, (n, k, d, u) in sorted(per_inst.items()):
        print(f"  {inst[:26]:26s} {n:5d} {k:5d} {d:5d} {u:4d}")
    total = sum(v[0] for v in per_inst.values())
    print(f"\ntotal rows: {total}, included: {sum(v[1] for v in per_inst.values())}, "
          f"excluded: {sum(v[2] for v in per_inst.values())}, "
          f"unmatched: {sum(v[3] for v in per_inst.values())}")

    if unknown:
        print("\ntitles not covered by data/titles.csv (add a rule for each):")
        for (country, title), n in unknown.most_common():
            print(f"  {n:3d}  {country}  {title!r}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
