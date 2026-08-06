# Source coverage audit — CSRankings

Snapshot: CSRankings `gh-pages`, retrieved 2026-08-06.
Raw files: `data/raw/csrankings/2026-08-06/`.
Derived: `data/derived/csrankings_europe.csv`, `data/derived/csrankings_europe_institutions.csv`.

**9,727 faculty rows across 223 in-scope institutions.** These are all CS faculty, before the
core-AI publication filter.

## Finding 1 — CSRankings institution granularity is organisational, not geographic

This is the single most damaging issue for a density ranking, because it silently assigns
people to the wrong city.

`Max Planck Society` is one CSRankings entity holding 57 people, and its member institutes sit
in at least eight different cities:

| Institute | City |
| --- | --- |
| MPI for Informatics, MPI for Software Systems | Saarbrücken |
| MPI for Software Systems (second site) | Kaiserslautern |
| MPI for Intelligent Systems, MPI for Biological Cybernetics | Tübingen |
| MPI for Intelligent Systems (second site) | Stuttgart |
| MPI for Security and Privacy | Bochum |
| MPI for Mathematics in the Sciences | Leipzig |
| MPI of Molecular Cell Biology and Genetics | Dresden |
| MPI for Human Development (Center for Humans and Machines) | Berlin |

Homepage domains disentangle this only partly — `mpi-sws.org` (11), `mpi-inf.mpg.de` (6),
`ps.is.tuebingen.mpg.de` (2), `mpi-sp.org` (2), `mpi-cbg.de` (2) resolve cleanly, but many
members use personal domains (`asiabiega.github.io`, `carmelatroncoso.com`,
`lasharavichander.github.io`) that carry no institutional signal.

**Consequence**: every Max Planck member needs individual institute resolution before they can
be geocoded. The same applies to `INRIA`. This is mandatory work, not an optional refinement.

## Finding 2 — Inria is covered at roughly a tenth of its real size

CSRankings lists 23 Inria researchers, 6 of them from `cambium.inria.fr` alone — the Paris
programming-languages team. Inria runs nine centres (Paris, Saclay, Grenoble, Rennes, Lille,
Sophia Antipolis, Nancy, Bordeaux, Lyon) and employs several hundred permanent researchers,
a large share of them in AI.

Anyone taking CSRankings at face value would conclude that French public AI research barely
exists. France shows only 12 in-scope institutions in the whole file, with Sorbonne,
Paris-Saclay, Université Paris Cité, Télécom Paris, Grenoble, and Toulouse all absent.

## Finding 3 — country code

CSRankings files the UK under `gb`, not `uk`. An `IN_SCOPE` set using `uk` silently drops all
43 British institutions and 2,813 faculty rows. Fixed in `scripts/fetch_csrankings.py`; noted
here because the failure mode is silent and the corrected total is nearly 40% larger.

## Finding 4 — CSRankings faculty counts are department size, not AI size

`Universidade de Lisboa` shows 278 faculty, `CRIStAL` 145, `University of A Coruña` 114.
These are whole CS departments. The core-AI publication filter, not the roster, does the
work of identifying AI researchers, so raw CSRankings counts must never be quoted as
AI headcounts.

## What this means for the budget

CSRankings substitutes for individual title verification only where its institution entity
maps to exactly one city. For the 223 in-scope institutions that holds everywhere except
`Max Planck Society` and `INRIA`.

The adjudication budget therefore goes to three places:

1. Per-person institute resolution for Max Planck (57) and Inria (23).
2. Faculty-directory reads for institutions absent from CSRankings — see
   `data/institutions_supplement.csv`.
3. Ambiguous individual cases surfaced by the automated passes.

## Finding 5 — MPI for Intelligent Systems is effectively invisible in CSRankings

Running the core-AI publication filter over the `Max Planck Society` entry gives the sharpest
result in this audit: **57 listed people, of whom 1 has a core-layer paper in the window.**

Spot-checking the institute's best-known PIs against the roster:

| Person | CSRankings affiliation |
| --- | --- |
| Bernhard Schölkopf | not listed |
| Michael J. Black | not listed |
| Moritz Hardt | not listed |
| Philipp Hennig | University of Tübingen |
| Matthias Hein | University of Tübingen |
| Jakob Macke | University of Tübingen |
| Georg Martius | University of Tübingen |

CSRankings' Max Planck entry captures the Saarbrücken CS institutes (MPI-INF, MPI-SWS), whose
strengths are theory, systems, and security. MPI-IS — the Max Planck AI institute, and the
reason Tübingen appears in any AI density discussion — contributes almost nothing to it, and
its directors are absent outright.

A CSRankings ∪ ELLIS union recovers these people only through the ELLIS side. That works for
Tübingen, which has an ELLIS unit, and fails silently anywhere that does not.

## Finding 6 — DBLP affiliation notes have high recall and poor precision

The affiliation-note sweep finds 6,985 core-active people with an in-scope affiliation, of whom
**5,593 are absent from the CSRankings roster** — including Schölkopf, Black, and Hardt. Inria
goes from 23 people to 113, which is much closer to reality.

The notes are cumulative and carry no dates, so they record every affiliation a person ever
had. Probing Tübingen returns 105 core-active people, and the senior end of that list is
full of researchers who left years ago:

| Returned for Tübingen | Actually at (2026) |
| --- | --- |
| Jan Peters | TU Darmstadt |
| Stefanie Jegelka | TU Munich |
| Francesco Locatello | ISTA |
| Suvrit Sra | TU Munich |
| Gjergji Kasneci | TU Munich |
| Kun Zhang | CMU |
| Zhijing Jin | Toronto |

**Consequence**: the free sources produce a candidate pool, never a roster. Precision has to
come from the adjudication pass, which is what the budget buys.

## Finding 7 — CSRankings affiliations are current

Checked against known recent moves, CSRankings has them right: Zeynep Akata is filed under
TU Munich, Francesco Locatello under IST Austria, Stefanie Jegelka under TU Munich. Where
CSRankings lists someone, both the title ruling and the location can be taken on trust.

## Implication for the OpenAlex pass

OpenAlex is worth running for **currency**, not recall. Its works carry per-paper institution
affiliations with dates, so restricting to 2024–2026 papers gives a dated answer to "where is
this person now" — exactly what DBLP's undated notes cannot supply. That turns the mover
problem from manual checking into a script.

## Candidate pool as it stands

| Layer | People | Adjudication needed |
| --- | --- | --- |
| CSRankings, core-active | 2,829 | Title and location trusted; only Max Planck and Inria members need institute resolution |
| DBLP affiliation notes, core-active, in scope, not in CSRankings | 5,593 | Full adjudication |
| **Total candidate pool** | **~8,400** | |

The pool is adjudicated **per institution**, not per person: one faculty-directory read per
institution yields the authoritative roster with titles, and the candidate pool is then joined
against it by script. That is roughly 185 directory reads, not 8,400 individual lookups.

## Bonus

52% of in-scope rows carry an ORCID, which resolves identity for free. Joining CSRankings to
DBLP succeeded for 9,471 of 9,727 people (97.4%) — 4,110 by ORCID, 5,361 by canonical name.
