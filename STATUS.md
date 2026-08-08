# Status — snapshot 2026-08-01, sources fetched 2026-08-06

## Where the project stands

Six German cities have been through the full protocol. Every counted person is a named row
with sources; every rejection carries a code and a reason. Nothing outside these six cities
is a result — the rest of Europe on the site is a CSRankings-only preview carrying every
bias documented in `audit/00-source-coverage.md`.

| City | PIs | Found by one source only | Status |
| --- | --- | --- | --- |
| München | 94 | 34 | reconciled |
| Saarbrücken | 37 | 9 | reconciled |
| Tübingen | 33 | 7 | reconciled |
| Berlin | 31 | 12 | reconciled |
| Stuttgart | 20 | 9 | reconciled |
| Kaiserslautern | 10 | 9 | reconciled |
| **Total** | **225** | | |

162 exclusions with codes: 89 not independent, 62 relocated, 11 unverifiable.
1,594 decisions in `data/decisions.jsonl`.

Counted at the ≥3 core-venue-papers threshold, 2021-01-01 to 2026-08-01. Density figures
depend enormously on the catchment radius — Tübingen reads 69.7 per 100k at 3 km and 1.8 at
40 km for the same people — which is why the site makes the reader draw the boundary.

## What is trustworthy, and what is not

**Reasonably settled.** The title ruling is applied from one table. Multi-site institutions
split per person from stated evidence. Cross-institution and alias duplicates are merged.
Cross-city moves are recorded at both ends. Every exclusion has a code.

**Known weak.** 80 of 225 counted people rest on a single source. The publication modality
can only place 24% of active authors, because DBLP affiliation notes are sparse, so recall
rests almost entirely on the institution rosters. Roster completeness has been measured
once, against CSRankings at CISPA: 15 of 15.

**Known gaps, recorded not closed.** Charité, Zuse-Institut, Fraunhofer HHI, MDC and BHT
host Berlin AI and none is collected. RPTU Kaiserslautern's own roster has never been read.
A systematic institution-coverage scan for all six cities was running when this was written;
its output lands in `data/raw/adjudication/2026-08-06/coverage/`.

## Open queues

None. The currency, independence and reconciliation queues were all cleared. Individual
rows flagged for a second look sit in the adjudication CSVs with `confidence=low` and a note
saying what is missing — search for those rather than assuming they were resolved.

## Next, in the order I would do it

1. **Close the coverage scan.** Collect whatever it names as "many", starting with RPTU
   Kaiserslautern, whose city currently rests on one institute.
2. **Raise the currency check's reach.** It resolves 57% of people; the rest fail OpenAlex
   author matching. ORCIDs would fix most of it.
3. **Then more cities.** The pipeline is codified — adding a city means editing
   `data/cities.csv` and running the loop in `RUNBOOK.md`. Zurich, Lausanne, Amsterdam,
   Paris-Saclay and London are the obvious next set, and Paris-Saclay is where CSRankings is
   most wrong.

## Things worth not relearning

- **Two paths computing the same city must agree.** Every disagreement so far was a defect,
  never a rounding difference.
- **A status must be earned.** Berlin was briefly labelled reconciled because an empty
  rulings file existed.
- **Verify the artifact, never the completion signal.** Both failure directions have
  occurred: an agent reporting success having written nothing, and an agent returning an
  incoherent summary with its files complete.
- **Geographic or national agreement is not identity.** A second, orthogonal check is
  always required — this cost four separate bugs before the shared vocabulary in
  `scripts/instnames.py` existed.
- **Half-done centralisation is worse than none**, because it looks finished. The city
  registry was extracted into one file and one of four consumers kept its private copy, so
  two cities' rulings were written and silently skipped.
