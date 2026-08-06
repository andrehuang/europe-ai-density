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

import re
import unicodedata
from collections import defaultdict


def fold(text):
    """Lowercase, strip diacritics, drop DBLP's homonym suffix and punctuation."""
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    stripped = re.sub(r"\s+\d{4}$", "", stripped)  # "jan peters 0001"
    stripped = re.sub(r"[^a-z ]+", " ", stripped)
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


class NameIndex:
    """Maps DBLP author names to a canonical form, refusing ambiguous keys."""

    def __init__(self):
        self.full = {}
        self.first_last = defaultdict(set)
        self.initial_last = defaultdict(set)
        self.ambiguous = 0

    def add(self, dblp_name):
        full, fl, il = keys_for(dblp_name)
        if not full:
            return
        self.full.setdefault(full, dblp_name)
        if fl:
            self.first_last[fl].add(dblp_name)
            self.initial_last[il].add(dblp_name)

    def resolve(self, name):
        """Return (dblp_name, how) or (None, reason)."""
        full, fl, il = keys_for(name)
        if not full:
            return None, "empty"
        if full in self.full:
            return self.full[full], "full"
        if fl and fl in self.first_last:
            hits = self.first_last[fl]
            if len(hits) == 1:
                return next(iter(hits)), "first_last"
            self.ambiguous += 1
            return None, f"ambiguous_first_last({len(hits)})"
        if il and il in self.initial_last:
            hits = self.initial_last[il]
            if len(hits) == 1:
                return next(iter(hits)), "initial_last"
            self.ambiguous += 1
            return None, f"ambiguous_initial_last({len(hits)})"
        return None, "no_match"
