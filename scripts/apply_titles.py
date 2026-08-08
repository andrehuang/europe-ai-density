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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from decisionlog import log_decision  # noqa: E402

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


def load_units():
    """Institute-published unit lists: which named groups are independent, which are not.

    A bare "Research Group Leader" cannot be ruled from the title, but the institutes
    themselves publish the distinction — MPI-INF separates D1-D6 from RG1-RG3, MPI-IS
    lists its departments apart from its independent groups. One structure page settles
    every ambiguous title at that institute, so the unit of the question is the institute
    and not the person.
    """
    path = (ROOT / "data" / "raw" / "adjudication" / "2026-08-06" / "mpi-groups" / "units.csv")
    kinds = {}
    if path.exists():
        for r in csv.DictReader(path.open(encoding="utf-8")):
            unit = fold(r["unit_name"]).replace(" sub group", "").strip()
            if unit:
                kinds[unit] = r["unit_kind"]
    return kinds


def alternatives(title):
    """Split a rule's title on " / ", which the registry uses to list equivalents.

    The separator is the spaced slash and only the spaced slash. Six rules carry a slash
    that belongs to the name itself — "Universitätsprofessor (W3/C4)", "Chargé de recherche
    (CNRS/Inria)" — and splitting those would leave "c4)" as a rule of its own.

    Without this, 28 rules were dead. Each was stored as one string, so "Akademischer Rat /
    Oberrat" could only ever match a title that literally read "Akademischer Rat / Oberrat",
    and a page saying "Akademischer Rat" fell through to unknown. The registry has always
    read as though it listed alternatives; now it does.
    """
    return [p.strip() for p in title.split(" / ") if p.strip()]


def load_rules():
    """country -> list of (folded title, counts_as_pi, tier, raw title)."""
    rules = defaultdict(list)
    for r in csv.DictReader((ROOT / "data" / "titles.csv").open(encoding="utf-8")):
        key = r["country"].upper()
        for part in alternatives(r["title_local"]):
            rules[key].append(
                (fold(part), r["counts_as_pi"], r["default_tier"], r["title_local"])
            )
        # The English gloss is also matchable: institute pages are often in English
        # even in non-anglophone countries.
        for part in alternatives(r["title_en"]):
            rules[key].append(
                (fold(part), r["counts_as_pi"], r["default_tier"], r["title_local"])
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
        # No "title is a substring of the rule" branch. It let a less specific title
        # inherit a more specific rule's ruling: a bare "Research Group Leader" matched
        # "Max Planck Research Group Leader" and with it the note "independent group with
        # own budget", admitting four members of Moritz Hardt's department as independent
        # PIs. A title that lacks the qualifier has not earned the qualifier's ruling.
    return None


def main() -> int:
    rules = load_rules()
    unit_kind = load_units()
    rosters = sorted(DIRS.glob("*/*/roster.csv"))
    if not rosters:
        print(f"no rosters under {DIRS}", file=sys.stderr)
        return 1

    out_rows = []
    unknown = Counter()
    per_inst = {}
    resolved_by_group = 0
    for path in rosters:
        inst_id = path.parent.name
        country = inst_id.split("-", 1)[0]
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        # A bare "group leader" title cannot be ruled from the words alone: at MPI-IS the
        # same string covers Michael Muehlebach, who leads his own group, and four members
        # of Moritz Hardt's department. The group name settles it. Anyone whose
        # group_or_dept is a unit that a director or department head owns is inside that
        # unit; anyone whose unit is their own is not.
        owned = {
            (r.get("group_or_dept") or "").strip().lower()
            for r in rows
            if re.search(r"\bdirector\b|departmentsleiter|abteilungsleiter|head of department",
                         (r.get("title_verbatim") or ""), re.I)
        }
        owned.discard("")
        kept = dropped = unmatched = 0
        for r in rows:
            title = r.get("title_verbatim", "")
            hit = rule_for(title, country, rules)
            if hit is None:
                hit = rule_for(normalise_title(title), country, rules)
            group = (r.get("group_or_dept") or "").strip().lower()
            if hit is None:
                verdict, tier, matched = "unknown", "", ""
                unknown[(country, title)] += 1
                unmatched += 1
            else:
                _, is_pi, tier, matched = hit
                verdict = ("include" if is_pi == "yes"
                           else "review" if is_pi == "review" else "exclude")
                if verdict == "review" and group:
                    # The institute's own unit list, where it has one.
                    k = unit_kind.get(fold(group))
                    if k == "independent_group":
                        verdict, matched = "include", matched + " (+institute unit list)"
                    elif k in ("department", "subteam"):
                        verdict, matched = "exclude", matched + " (+institute unit list)"
                # A group-versus-department heuristic was tried here and removed. It
                # only works when the department's director appears in the same roster
                # file, and at MPI-IS Tübingen he does not — so it silently defaulted to
                # admitting everyone, which is the failure it was written to prevent.
                # This class needs per-person evidence, not a rule over the data on hand.
                kept += verdict == "include"
                dropped += verdict == "exclude"
                unmatched += verdict == "review"
            log_decision(city="", person=r.get("name", ""), decision=verdict,
                         reason_code="", rule=(matched or "unmatched title"),
                         evidence=r.get("evidence_url", ""), by=f"apply_titles.py:{inst_id}",
                         note=f"title as written: {title!r}")
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
