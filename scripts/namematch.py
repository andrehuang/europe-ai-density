#!/usr/bin/env python3
"""Name resolution between scraped rosters and DBLP.

Exact string matching silently drops people. DBLP writes "Jakob H. Macke" while an
institute page writes "Jakob Macke", and the difference reads as zero publications —
which would quietly disqualify a director.

Three keys are tried in order, most specific first:
  1. the full folded name
  2. (first token, last token), which absorbs middle names and initials
  3. (first initial, last token), which absorbs a shortened or localised given name

Keys 2 and 3 are ambiguous by construction, so a key that maps to more than one DBLP
person is refused rather than guessed. Refusals are counted, not hidden.
"""

import csv
import gzip
import re
import unicodedata

from instnames import city_key
from collections import defaultdict


# Academic title prefixes, which institution directories fold into the name field.
# DFKI writes "Prof. Dr.-Ing. Philipp Slusallek" where the university writes "Philipp
# Slusallek", and without stripping these the same person is counted twice.
TITLE_PREFIX = re.compile(
    r"^(?:"
    r"prof(?:essor)?|dr|drs|ing|dipl|mag|phd|md|pd|priv|doz|doc|univ|apl|hon|em|"
    r"herr|frau|mr|mrs|ms|sir|dame|assoc|asst|assistant|associate|senior|junior"
    r")\b[\s.]*"
)


def fold(text):
    """Lowercase, strip diacritics, drop DBLP's homonym suffix, titles and punctuation."""
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    stripped = re.sub(r"\s+\d{4}$", "", stripped)  # "jan peters 0001"
    stripped = re.sub(r"[^a-z ]+", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    # Titles stack: "Prof. Dr.-Ing." needs several passes, but stop if nothing is left,
    # since a few real surnames collide with title words.
    for _ in range(4):
        shorter = TITLE_PREFIX.sub("", stripped).strip()
        if not shorter or shorter == stripped:
            break
        stripped = shorter
    return stripped


def fold_keep_suffix(text):
    """Fold for comparison but keep DBLP's homonym suffix, which is part of identity."""
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    stripped = re.sub(r"[^a-z0-9 ]+", " ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def keys_for(name):
    """Return (full, first_last, initial_last) keys for a name."""
    f = fold(name)
    if not f:
        return None, None, None
    parts = [p for p in f.split(" ") if len(p) > 0]
    if len(parts) < 2:
        return f, None, None
    # Drop single-letter tokens when forming the first/last key so that
    # "jakob h macke" and "jakob macke" agree.
    meaningful = [p for p in parts if len(p) > 1]
    if len(meaningful) < 2:
        meaningful = parts
    first_last = (meaningful[0], meaningful[-1])
    initial_last = (meaningful[0][0], meaningful[-1])
    return f, first_last, initial_last


def seeded_index(persons_gz):
    """Build an index from EVERY DBLP person record, with their current affiliations.

    Three scripts each carried their own copy of this loop and each skipped person
    records that had no alias, so the authoritative layer held only a small minority of
    DBLP and homonyms were settled by whichever spelling the authorship pass reached
    first. That is how "Matthias Hein" — three distinct people, none with an alias —
    resolved to the TU Ilmenau physicist on three Tübingen rosters while the MPI-IS
    professor with 33 core papers appeared in neither the count nor the exclusions.

    Centralised for the same reason the city registry was: a rule copied into three
    files is a rule that will be fixed in two of them.

    Returns (index, affiliations) where affiliations maps a primary name to DBLP's
    current-affiliation string, which callers use to break homonym ties on evidence.
    """
    index, aff = NameIndex(), {}
    with gzip.open(persons_gz, "rt", encoding="utf-8") as fh:
        for p in csv.DictReader(fh):
            index.add_person(p["primary_name"],
                             [a for a in (p.get("aliases") or "").split("|") if a])
            if p.get("affiliations_current"):
                aff[p["primary_name"]] = p["affiliations_current"]
    return index, aff


class NameIndex:
    """Maps DBLP author names to a canonical form, refusing ambiguous keys."""

    def __init__(self):
        # Keyed on the name *including* DBLP's homonym suffix. That suffix is identity,
        # not noise: "Matthias Hein 0001" runs a machine-learning group at MPI-IS in
        # Tübingen and "Matthias Hein 0002" is at TU Ilmenau. Folding it away made them
        # one key, and whichever was indexed first silently won — which put the Ilmenau
        # physicist in Tübingen's roster.
        self.exact = {}
        self.full = defaultdict(set)
        self.first_last = defaultdict(set)
        self.initial_last = defaultdict(set)
        self.ambiguous = 0

    def add(self, dblp_name, canonical=None, weak=False):
        """Register a name form. `canonical` lets an alias resolve to the primary name.

        `weak` marks a name harvested from a publication's author string rather than from
        a DBLP person record. Those must not overwrite or compete with what a person
        record already established: DBLP knows "Alois Knoll" is an alias of "Alois C.
        Knoll", and re-adding the bare form from the authorship pass made the key
        ambiguous, so the matcher refused it and the same man was counted twice in Munich.
        """
        target = canonical or dblp_name
        full, fl, il = keys_for(dblp_name)
        if not full:
            return
        if weak and (full in self.full or fold_keep_suffix(dblp_name) in self.exact):
            return
        self.exact.setdefault(fold_keep_suffix(dblp_name), target)
        self.full[full].add(target)
        if fl:
            self.first_last[fl].add(target)
            self.initial_last[il].add(target)

    def add_person(self, primary_name, aliases=()):
        """Register a DBLP person record so every alias collapses to one identity.

        This matters because upstream sources carry alias duplicates. CSRankings lists
        Hilde Kuehne three times — as "Hilde Kuehne", "Hildegard Kuehne" and "Hildegard
        Koehler", all with the same DBLP pid and the same publication count. An index
        seeded only from publication author strings knows just the first form, so the
        other two become separate people and the city is counted up to three times.
        """
        self.add(primary_name)
        for alias in aliases:
            if alias:
                self.add(alias, canonical=primary_name)

    def candidates(self, name):
        """The identities a name could denote, best key first.

        resolve() refuses an ambiguous key, which is right when nothing else is known. A
        caller that holds independent evidence — the institution a roster belongs to — can
        use this to break the tie on that evidence instead of losing the person. Returns
        an empty set when the name is unknown rather than ambiguous.
        """
        full, fl, il = keys_for(name)
        if not full:
            return set()
        # Union, not first-key-wins. A roster reading "Hendrik Lensch" matches a sparse
        # person record of exactly that name on the full key and stops, never reaching the
        # first/last key where "Hendrik P. A. Lensch" lives. Both are candidates; which one
        # the roster means is for the caller's evidence to decide, not for key precedence.
        out = set(self.full.get(full, ()))
        if fl:
            out |= set(self.first_last.get(fl, ()))
        return out

    def resolve(self, name):
        """Return (dblp_name, how) or (None, reason)."""
        full, fl, il = keys_for(name)
        if not full:
            return None, "empty"
        # A query carrying a homonym suffix is unambiguous by construction. A query
        # without one must NOT prefer the unsuffixed DBLP entry: that entry is itself a
        # specific person, not a wildcard. A roster reading "Shiwei Liu" matched DBLP's
        # bare "Shiwei Liu" — two papers — while the ELLIS Institute group leader is
        # "Shiwei Liu 0003" with forty-eight.
        if re.search(r"\s\d{4}$", (name or "").strip()):
            exact = self.exact.get(fold_keep_suffix(name))
            if exact:
                return exact, "exact"
        if full in self.full:
            hits = self.full[full]
            if len(hits) == 1:
                return next(iter(hits)), "full"
            self.ambiguous += 1
            return None, f"ambiguous_full({len(hits)})"
        if fl and fl in self.first_last:
            hits = self.first_last[fl]
            if len(hits) == 1:
                return next(iter(hits)), "first_last"
            self.ambiguous += 1
            return None, f"ambiguous_first_last({len(hits)})"
        # The initial/surname key may only expand an abbreviation, never contract a full
        # given name. Allowing the latter merged "Verena Wolf" into "Valentin Wolf",
        # because ("v", "wolf") had exactly one candidate — a false identity merge, which
        # is worse than no merge at all. A shared surname and initial is not identity.
        if il and len(fl[0]) == 1 and il in self.initial_last:
            hits = self.initial_last[il]
            if len(hits) == 1:
                return next(iter(hits)), "initial_last"
            self.ambiguous += 1
            return None, f"ambiguous_initial_last({len(hits)})"
        return None, "no_match"

def city_named_in(affiliation, city):
    """True when a DBLP affiliation string names this city, compared on whole tokens.

    Through city_key, so exonyms agree: an entry reading "Muenchen", "Munchen" or
    "Munich" all match a registry city of "München". Whole tokens only — a substring
    test makes every "Essen" a hit inside "Giessen".
    """
    if not affiliation or not city:
        return False
    want = city_key(city)
    return any(city_key(tok) == want
               for tok in re.split(r"[^A-Za-z\u00C0-\u00FF]+", affiliation) if tok)


def resolve_with_city(index, aff, name, city):
    """resolve(), with homonym ties broken by DBLP's own affiliation strings.

    Applied whenever the current answer does not name the city, whether that answer is a
    refusal or a confident match, because both failure modes occur and both were silent:

    - "Matthias Hein" is one of three homonyms and was refused, while the Tübingen
      professor among them holds 33 core papers.
    - "Hendrik Lensch" matched a sparse DBLP record of exactly that name, so the full key
      resolved and never reached the first/last key where "Hendrik P. A. Lensch" lives.

    Evidence beats key precedence, but only when it is decisive: exactly one candidate
    naming the city settles it; two, or none, leaves the original answer alone. Where DBLP
    records no affiliation for anyone involved — Björn Schuller's entry names Imperial and
    Augsburg, never Munich — this cannot help, and the row belongs in the identity queue
    for a person to settle.
    """
    resolved, how = index.resolve(name)
    if city and not city_named_in(aff.get(resolved, ""), city):
        hits = [c for c in index.candidates(name) if city_named_in(aff.get(c, ""), city)]
        if len(hits) == 1:
            return hits[0], "affiliation"
    return resolved, how
