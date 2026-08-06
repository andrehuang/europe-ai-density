#!/usr/bin/env python3
"""Join scraped rosters to DBLP and report what survives the core-AI filter.

Reports two things the project needs to know before trusting a directory pass:
how many roster names resolve to a DBLP person at all, and how many clear the
activity threshold. A low resolution rate means the name matcher is at fault; a low
survival rate with high resolution means the directory over-collected, which is fine.
"""

import csv
import gzip
import pathlib
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from namematch import NameIndex  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
CORE_MIN = 3


def main() -> int:
    index = NameIndex()
    core = Counter()
    extended = Counter()
    with gzip.open(DERIVED / "dblp_venue_authorships.csv.gz", "rt", encoding="utf-8") as fh:
        for a in csv.DictReader(fh):
            name = a["author"]
            if not name:
                continue
            index.add(name)
            if a["layer"] == "core" and a["is_findings"] == "0":
                core[name] += 1
            else:
                extended[name] += 1
    print(f"DBLP author names indexed: {len(index.full)}")

    roots = sorted((ROOT / "data" / "raw" / "directories").glob("*/"))
    rows_out = []
    for root in roots:
        for path in sorted(root.glob("*/roster.csv")):
            inst_id = path.parent.name
            run = root.name
            rows = list(csv.DictReader(path.open(encoding="utf-8")))
            how = Counter()
            active = 0
            for r in rows:
                resolved, reason = index.resolve(r.get("name", ""))
                how[reason if resolved is None else reason] += 1
                n = core.get(resolved, 0) if resolved else 0
                if n >= CORE_MIN:
                    active += 1
                rows_out.append(
                    {
                        "run": run,
                        "inst_id": inst_id,
                        "name": r.get("name", ""),
                        "dblp_name": resolved or "",
                        "match": reason,
                        "title_verbatim": r.get("title_verbatim", ""),
                        "core_papers": n,
                        "extended_papers": extended.get(resolved, 0) if resolved else 0,
                        "evidence_url": r.get("evidence_url", ""),
                    }
                )
            resolved_n = sum(v for k, v in how.items() if k in ("full", "first_last", "initial_last"))
            print(
                f"  {run:20s} {inst_id[:22]:24s} rows={len(rows):3d} "
                f"resolved={resolved_n:3d} active(>={CORE_MIN})={active:3d}  {dict(how)}"
            )

    out = DERIVED / "roster_checked.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
