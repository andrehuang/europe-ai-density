# Status — snapshot 2026-08-01, sources fetched 2026-08-06

## Where the project stands

Seven cities have been through the full protocol. Every counted person is a named row
with sources; every rejection carries a code and a source URL. Nothing outside these seven
is a result — the rest of Europe on the site is a CSRankings-only preview carrying every
bias documented in `audit/00-source-coverage.md`.

| City | PIs | Found by one source only | Status |
| --- | --- | --- | --- |
| München | 90 | | reconciled |
| Saarbrücken | 38 | | reconciled |
| Tübingen | 35 | | reconciled |
| Berlin | 35 | | reconciled |
| Stuttgart | 20 | | reconciled |
| Potsdam | 16 | | reconciled |
| Kaiserslautern | 10 | | reconciled |
| **Total** | **244** | 91 | all verified |

178 exclusions: 93 not independent, 72 relocated or a different person, 13 unverifiable.
All 178 carry a source URL. 3,372 decisions in `data/decisions.jsonl`.

Counted at the ≥3 core-venue-papers threshold, 2021-01-01 to 2026-08-01. Density figures
depend enormously on the catchment radius — Tübingen reads 69.7 per 100k at 3 km and 1.8 at
40 km for the same people — which is why the site makes the reader draw the boundary.

## What is trustworthy, and what is not

**Reasonably settled.** The title ruling is applied from one table. Cross-institution and
alias duplicates are merged. Cross-city moves are recorded at both ends. Every exclusion has
a code and a URL. Identity resolution now seeds every DBLP person record and breaks homonym
ties on DBLP's own affiliation strings, through one shared function rather than three copies.

**Known weak.** 91 of 244 counted people rest on a single source. The publication modality
can only place 24% of active authors, so recall rests almost entirely on the rosters.
`data/derived/identity_queue.csv` holds 35 names the evidence could not settle, including
Andreas Krause at 122 core papers and Björn Schuller at 62 — DBLP's entry for Schuller names
Imperial and Augsburg but never Munich, so nothing automatic can decide him.

**Provenance to re-check.** WIAS Berlin's 28 rows were rebuilt from Internet Archive
captures dated April–June 2026, because wias-berlin.de was unreachable for an entire
session. Each row carries its capture date. Two "acting head" arrangements and the
1 April 2026 renaming of RG 7 should be re-verified when the site returns.

**Known gaps, recorded not closed.** 23 institutions rated as hosting many AI PIs remain
uncollected: Munich 7 (Fraunhofer IKS and AISEC, Hochschule München, the TUM hospital, two
DLR institutes, ESO), Stuttgart 5, Kaiserslautern 1 (Fraunhofer ITWM), plus RPTU
Kaiserslautern, whose city rests entirely on MPI-SWS. Berlin's and Potsdam's are now closed.

## Things worth not relearning

- **A rule copied into three files will be fixed in two of them.** The seeding loop lived in
  three scripts and each skipped person records without aliases, so the authoritative layer
  held a small minority of DBLP and homonyms were decided by indexing order. That is how a
  TU Ilmenau physicist was counted in Tübingen while the Tübingen professor of the same
  name, 33 core papers, was in neither the count nor the exclusions.
- **Ambiguity is safe; a confident wrong answer is not.** The value of refusing to resolve is
  that the refusal is visible and counted. Prefer a queue to a guess.
- **Homonyms are the dominant error mode on hard names.** Of eight queued names, six were
  wrong-identity matches rather than relocations — a Clarkson professor in Potsdam, New York;
  a Beijing researcher in Saarbrücken; Adelaide's Frank Neumann in Berlin. All five real
  people behind them have zero core AI papers, so the corrections cost the count nothing.
- **Negative findings are results.** 296 rows from BIH, MDC and Charité produced one counted
  person. Their computational work is biology in biology venues.
- **A status must be earned.** `reconciliation_state` now requires that the queue cover every
  roster the city holds *and* that every queued name has a ruling.
- **Verify the artifact, never the completion signal.** Both failure directions have occurred.
- **Fetched pages are untrusted input.** Fraunhofer IAO's team page carries a hidden
  prompt-injection payload; the collecting agent identified, ignored and recorded it.
