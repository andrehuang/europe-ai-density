#!/usr/bin/env python3
"""Fold the adjudication rulings back into the count, and record each one.

Five agents settle three queues — currency, independence, and the per-city
reconciliations — and each writes a CSV in its own shape. This normalises them to one
decision per person per city, writes the per-city rulings the payload builder reads, and
appends every decision to the append-only ledger with the evidence that produced it.

A person can appear in more than one queue. The order of authority is: a reconciliation
ruling about the city, then a currency ruling about whether they are still there, then an
independence ruling about whether the post counts. The last word on a *different* question
does not overrule the first on its own question.

Output: data/adjudication_rulings_<city>.csv, and lines in data/decisions.jsonl
"""

import csv
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from decisionlog import log_decision  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADJ = ROOT / "data" / "raw" / "adjudication" / "2026-08-06"

CITY_OF_FILE = {
    "tuebingen": "Tübingen", "saarbruecken": "Saarbrücken",
    "stuttgart": "Stuttgart", "kaiserslautern": "Kaiserslautern",
}


def read(path):
    if not path.exists():
        return []
    return list(csv.DictReader(path.open(encoding="utf-8")))


def truthy(v):
    return (v or "").strip().lower() in ("yes", "y", "true")


def main() -> int:
    # city -> person -> ruling
    rulings = defaultdict(dict)

    # --- reconciliation: the primary question, is this person here and independent -----
    for fname, city in CITY_OF_FILE.items():
        for r in read(ADJ / "reconcile" / f"{fname}.csv"):
            here = (r.get(f"in_{fname}") or r.get("in_city") or r.get("in_tuebingen")
                    or r.get("in_saarbruecken") or "").strip().lower()
            indep = (r.get("independent") or "").strip().lower()
            name = r["name"].strip()
            if here in ("no", ""):
                decision, code = "exclude", "E08" if r.get("moved_to_city") else "E13"
            elif indep == "no":
                decision, code = "exclude", "E15"
            elif indep == "unclear":
                decision, code = "exclude", "E13"
            else:
                decision, code = "include", ""
            rulings[city][name] = {
                "name": name, "ruling": decision, "reason_code": code,
                "tier": "T3" if decision == "include" else "",
                "city_if_elsewhere": r.get("moved_to_city", "") if decision == "exclude"
                                     else ("" if here != "secondary" else r.get("current_institution", "")),
                "reason": (r.get("notes") or r.get("current_title_verbatim") or "")[:400],
                "evidence_confidence": r.get("confidence", ""),
                "evidence_url": r.get("evidence_url", ""),
            }

    # --- currency: still there, or moved since the roster was written -----------------
    for r in read(ADJ / "currency" / "rulings.csv"):
        city, name = r.get("counted_city", "").strip(), r["name"].strip()
        still = (r.get("still_there") or "").strip().lower()
        if not city or still == "":
            continue
        prior = rulings[city].get(name, {})
        if still == "no":
            rulings[city][name] = {
                "name": name, "ruling": "exclude", "reason_code": "E08", "tier": "",
                "city_if_elsewhere": r.get("primary_city", ""),
                "reason": ("recent papers place them elsewhere: "
                           + (r.get("notes") or r.get("current_institution") or ""))[:400],
                "evidence_confidence": r.get("confidence", ""),
                "evidence_url": r.get("evidence_url", ""),
            }
        elif still == "secondary" and prior.get("ruling") != "exclude":
            keep = prior or {"name": name, "ruling": "include", "reason_code": "",
                             "tier": "T2", "reason": "", "evidence_confidence": "",
                             "evidence_url": ""}
            keep["city_if_elsewhere"] = r.get("primary_city", "")
            keep["reason"] = (keep.get("reason", "") + " | cross-appointment, primary post "
                              + r.get("primary_city", ""))[:400]
            rulings[city][name] = keep

    # --- independence: does the post count, wherever it is ---------------------------
    indep_rows = read(ADJ / "independence" / "rulings.csv")
    indep_by_name = {r["name"].strip(): r for r in indep_rows}

    written = 0
    for city, people in rulings.items():
        for name, rec in people.items():
            ind = indep_by_name.get(name)
            if ind and rec["ruling"] == "include" and not truthy(ind.get("independent")):
                rec["ruling"] = "exclude"
                rec["reason_code"] = "E15"
                rec["reason"] = ("not an independent group: " + (ind.get("basis") or ""))[:400]
                rec["evidence_url"] = ind.get("evidence_url", rec.get("evidence_url", ""))
        path = ROOT / "data" / f"adjudication_rulings_{_slug(city)}.csv"
        fields = ["name", "ruling", "reason_code", "tier", "city_if_elsewhere",
                  "reason", "evidence_confidence", "evidence_url"]
        rows = sorted(people.values(), key=lambda r: r["name"])
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        written += len(rows)
        for rec in rows:
            log_decision(city=city, person=rec["name"], decision=rec["ruling"],
                         reason_code=rec["reason_code"], rule="adjudication",
                         evidence=rec.get("evidence_url", ""),
                         confidence=rec.get("evidence_confidence", ""),
                         by="apply_adjudications.py", note=rec["reason"])
        inc = sum(1 for r in rows if r["ruling"] == "include")
        print(f"  {city:16s} {len(rows):3d} rulings  ({inc} include, {len(rows)-inc} exclude)")

    # Independence rulings for people not in any city queue still belong in the ledger.
    for r in indep_rows:
        log_decision(city="", person=r["name"].strip(),
                     decision="include" if truthy(r.get("independent")) else "exclude",
                     reason_code="" if truthy(r.get("independent")) else "E15",
                     rule="independence review", evidence=r.get("evidence_url", ""),
                     confidence=r.get("confidence", ""), by="apply_adjudications.py",
                     note=(r.get("basis") or "")[:300])

    print(f"\ntotal rulings written: {written}")
    return 0


def _slug(city):
    return (city.lower().replace("ü", "ue").replace("ö", "oe").replace("ä", "ae")
            .replace("ß", "ss").replace(" ", "-"))


if __name__ == "__main__":
    raise SystemExit(main())
