#!/usr/bin/env python3
"""Append-only ledger of every inclusion decision.

Until now a decision lived wherever it was made: a verdict in a derived file that the
next run overwrote, a hand-written ruling in a CSV, a sentence in a commit message. When
the same person was ruled in, then out, then in again as the rules changed, nothing in
the data said so — only git history and prose.

This ledger answers "why is this person counted, and what did we think before?" from the
data itself. It is append-only: a decision is never edited or deleted, it is superseded,
and the superseded entry stays.

  from decisionlog import log_decision
  log_decision(city="Tübingen", person="Yong Cao 0001", decision="exclude",
               reason_code="E15", rule="titles.csv XX Group Leader",
               evidence="https://...", by="reconcile_city.py", confidence="high",
               note="postdoc leading a sub-team inside another chair")

Query it:
  python3 scripts/decisionlog.py "Yong Cao"        # one person's full history
  python3 scripts/decisionlog.py --city Tübingen   # a city's current decisions
  python3 scripts/decisionlog.py --flips           # people whose decision changed
"""

import hashlib
import json
import os
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "decisions.jsonl"

# The snapshot the project is pinned to. Wall-clock time is deliberately not used: a
# rerun of the same pipeline over the same inputs must produce the same ledger lines,
# so the entries can be deduplicated instead of accumulating on every run.
SNAPSHOT = "2026-08-01"


def _fingerprint(entry):
    """Stable id for a decision, so reruns do not duplicate it."""
    key = "|".join(str(entry.get(k, "")) for k in
                   ("city", "person", "decision", "reason_code", "rule", "by", "evidence"))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _load():
    if not LEDGER.exists():
        return []
    out = []
    with LEDGER.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def log_decision(city, person, decision, by, reason_code="", rule="", evidence="",
                 confidence="", note="", run=SNAPSHOT):
    """Append a decision unless an identical one is already recorded."""
    entry = {
        "run": run, "city": city, "person": person, "decision": decision,
        "reason_code": reason_code, "rule": rule, "evidence": evidence,
        "confidence": confidence, "by": by, "note": note,
    }
    entry["id"] = _fingerprint(entry)
    existing = {e["id"] for e in _load()}
    if entry["id"] in existing:
        return entry["id"]
    # A different decision for the same person supersedes the previous one, and says so.
    prior = [e for e in _load() if e["person"] == person and e["city"] == city]
    if prior:
        entry["supersedes"] = prior[-1]["id"]
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry["id"]


def history(query):
    rows = [e for e in _load() if query.lower() in e["person"].lower()]
    if not rows:
        print(f"no decisions recorded for {query!r}")
        return
    for e in rows:
        flag = "  (superseded earlier decision)" if e.get("supersedes") else ""
        print(f"[{e['decision']:8s}] {e['person']}  ({e['city']}){flag}")
        print(f"    code {e['reason_code'] or '—'} · rule {e['rule'] or '—'} · by {e['by']}")
        if e["evidence"]:
            print(f"    evidence {e['evidence']}")
        if e["note"]:
            print(f"    {e['note']}")


def current(city=None):
    latest = {}
    for e in _load():
        if city and e["city"] != city:
            continue
        latest[(e["city"], e["person"])] = e
    counts = defaultdict(int)
    for e in latest.values():
        counts[(e["city"], e["decision"])] += 1
    for (c, d), n in sorted(counts.items()):
        print(f"  {c:16s} {d:8s} {n:4d}")


def flips():
    seen = defaultdict(list)
    for e in _load():
        seen[(e["city"], e["person"])].append(e)
    n = 0
    for (c, p), es in seen.items():
        decisions = [e["decision"] for e in es]
        if len(set(decisions)) > 1:
            n += 1
            print(f"  {p}  ({c}): {' -> '.join(decisions)}")
            print(f"      last reason: {es[-1]['note'] or es[-1]['reason_code']}")
    print(f"\n{n} people whose decision changed")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        current()
    elif args[0] == "--city":
        current(args[1])
    elif args[0] == "--flips":
        flips()
    else:
        history(" ".join(args))
