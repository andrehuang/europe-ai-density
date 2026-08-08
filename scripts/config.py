#!/usr/bin/env python3
"""One place that knows the cities, the snapshot, and the paths.

The city definition used to live in four scripts at once. Adding a city meant editing all
four, and forgetting one was invisible: build_site_payload applied adjudication rulings
only for Tübingen because of a leftover gate, so five cities' rulings were written and
silently ignored, and finalize_city knew only Tübingen and raised KeyError for the rest —
which went unnoticed because the run that called it discarded stderr.

Everything that needs to know what a city is made of reads data/cities.csv through here.
"""

import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DERIVED = DATA / "derived"
RAW = DATA / "raw"

# The date the sources were fetched. Used to name snapshot directories, and pinned rather
# than taken from the clock so a rerun reproduces the same paths.
SNAPSHOT = "2026-08-06"
# The date a person must have held their position on, for the count.
AS_OF = "2026-08-01"
CORE_MIN = 3

DIRECTORIES = RAW / "directories" / SNAPSHOT
ADJUDICATION = RAW / "adjudication" / SNAPSHOT


def _split(value, sep="|"):
    return [v for v in (value or "").split(sep) if v]


def _site_filters(value):
    """"inst:column:allowed;allowed" pairs -> {inst: (column, (allowed, ...))}."""
    out = {}
    for part in _split(value):
        bits = part.split(":")
        if len(bits) == 3:
            inst, column, allowed = bits
            out[inst] = (column, tuple(allowed.split(";")))
    return out


def cities():
    """Ordered mapping of city name -> its definition."""
    out = {}
    for r in csv.DictReader((DATA / "cities.csv").open(encoding="utf-8")):
        out[r["city"]] = {
            "slug": r["slug"],
            "rosters": tuple(_split(r["rosters"])),
            "csrankings": tuple(_split(r["csrankings_affiliations"])),
            "site_filters": _site_filters(r["site_filters"]),
            "dblp_pattern": r["dblp_pattern"],
            "notes": r["notes"],
        }
    return out


def city_by_slug(slug):
    for name, cfg in cities().items():
        if cfg["slug"] == slug:
            return name, cfg
    raise KeyError(f"unknown city slug {slug!r}; known: "
                   f"{[c['slug'] for c in cities().values()]}")


def reconciliation_state(city):
    """('reconciled' | 'stale' | 'none', detail) for this city.

    Three things have each, at some point, been mistaken for a finished reconciliation:

    - a rulings file merely existing, which briefly earned Berlin the label while empty;
    - a reconciliation that was genuine but predates rosters collected since, which is the
      failure this function was extended to catch — Berlin went from 6 rosters to 15, and
      the old queue had never seen nine of them;
    - a city whose queue was never run at all.

    Staleness is decided by mtime: any roster newer than the reconcile queue was not part
    of what was reconciled. That is the same invariant deploy_site.sh applies to the page
    and its payload, and it is cheap precisely because it needs no bookkeeping to stay true.
    """
    cfg = cities()[city]
    queue = ADJUDICATION / "reconcile" / f"{cfg['slug']}.csv"
    if not queue.exists():
        return "none", "no reconciliation queue"

    # Preferred: the roster set the queue was actually generated from, written by
    # reconcile_city.py. Anything the city has gained since was never reconciled.
    covered = DERIVED / f"reconcile_{cfg['slug']}.rosters"
    if covered.exists():
        seen = set(covered.read_text(encoding="utf-8").split())
        missing = [i for i in cfg["rosters"] if i not in seen]
        if missing:
            return "stale", (f"{len(missing)} roster(s) added since it ran: "
                             f"{', '.join(sorted(missing))}")
        return "reconciled", ""

    # Fallback for queues that predate the sidecar. Weaker, because any later edit to the
    # queue file resets the comparison — which is why the sidecar exists.
    queue_mtime = queue.stat().st_mtime
    newer = [i for i in cfg["rosters"]
             if (p := DIRECTORIES / i / "roster.csv").exists()
             and p.stat().st_mtime > queue_mtime]
    if newer:
        return "stale", f"{len(newer)} roster(s) collected after it: {', '.join(sorted(newer))}"
    return "reconciled", " (by mtime; no roster sidecar)"


def is_reconciled(city):
    """True only when the queue was worked and covers every roster the city now has."""
    return reconciliation_state(city)[0] == "reconciled"
