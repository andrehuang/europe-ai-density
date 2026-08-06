# Tübingen — city audit

Snapshot 2026-08-01. First city taken through the full protocol, and the calibration case
for everything that follows.

**47 verified PIs. 52 candidates excluded, each with a reason code and a source.**

## Sources

| Source | Rows | ≥3 core papers |
| --- | --- | --- |
| Tübingen AI Center directory | 32 | 25 |
| CSRankings, University of Tübingen | — | 21 |
| MPI for Intelligent Systems, Tübingen campus | 20 | 17 |
| ELLIS Institute Tübingen | 14 | 14 |
| ELLIS Unit Tübingen | 12 | 11 |
| Adjudication of the reconciliation queue | 20 | 2 admitted |

Five overlapping sources, which is why this city can be published with confidence. Even so,
**22 of the 47 people (46%) were found by exactly one source.** Michael Black appears only via
ELLIS; Kerstin Ritter and Georg Martius only via the Tübingen AI Center. A city with one
source has no equivalent safety net, and its roster should not be read as comparably complete.

## What the reconciliation caught

Two people hold independent positions in Tübingen and appear on **none** of the five
directories. Both were recovered only because the publication-driven modality flagged them:

- **Yong Cao** — Group Leader for NLP, University of Tübingen
- **Harrisen Scells** — W1-Juniorprofessur für Humansprachtechnologie, University of Tübingen

Without the second modality the city would have been reported at 45 with no indication that
anything was missing.

## Exclusions

| Code | Meaning | Count |
| --- | --- | --- |
| E08 | Relocated before the snapshot | 33 |
| E02 | Doctoral student | 11 |
| E01 | Postdoc | 2 |
| E15 | Not independent | 2 |
| E07 | Outside the geographic scope | 2 |
| E13 | Could not verify | 1 |
| E06 | Corporate only | 1 |

Six of the excluded count toward another city instead, and are recorded so that the
cross-city bookkeeping stays consistent: Dmitry Kobak → Ghent, Steffen Schneider → Munich,
Leena Vankadara → London, Guy Moss → Berlin, Mijung Park → Vancouver (out of scope),
Shashank Singh → New York (out of scope).

E08 dominating the exclusions is the expected shape. DBLP affiliation notes are cumulative,
so a city that trains and exports many researchers accumulates a long tail of people who
publish under its name years after leaving. Tübingen exports heavily: Zeynep Akata and
Debarghya Ghoshdastidar to Munich, Jan Peters to Darmstadt, Francesco Locatello to ISTA,
Kun Zhang to CMU, Stefanie Jegelka and Suvrit Sra to Munich and MIT.

## Contested and unresolved

- **Chris Gagne** — excluded at low confidence. A former Dayan postdoc who left around
  September 2022; current employer contradictory across sources. Revisit.
- **Bernhard Jaeger** — excluded under E13. Describes himself as a startup co-founder while
  publishing with the Autonomous Vision group; independence not established.
- **Ilia A. Petrov** — the DBLP identifier `Ilia A. Petrov 0001` may collide with a Reutlingen
  professor of a similar name. Excluded as a doctoral candidate per the identifier used;
  flagged because the collision would matter if the other person were in scope.
- **Roland S. Zimmermann** — Senior Research Scientist inside another group; current
  institution unconfirmed.
- **Institutional attribution conflicts.** The Tübingen AI Center attributes Abdelnabi,
  Andriushchenko, Dax, Shiwei Liu, Mendler-Dünner, Orvieto and Rusch to the ELLIS Institute,
  while the MPI-IS directory claims several of them. The two sit on the same campus and share
  pages. **The city count is unaffected** — everyone is in Tübingen and is counted once — but
  any statement about how many PIs MPI-IS has needs the official rosters to settle it.

## Density depends entirely on the radius

Population from GHS-POP, summed over the union of discs around the cluster's institutions.

| Catchment radius | Population | PIs per 100k |
| --- | --- | --- |
| 3 km | 67,414 | **69.72** |
| 5 km | 81,188 | 57.89 |
| 10 km | 172,999 | 27.17 |
| 15 km | 419,683 | 11.20 |
| 25 km | 1,066,590 | 4.41 |
| 40 km | 2,651,608 | 1.77 |

A factor of thirty-nine between the tightest and widest reading of the same city. No single
radius is correct, which is the argument for letting the reader draw the boundary rather than
publishing one number and defending it. The 15 km figure is the default only because it is the
same default applied everywhere.

## Known limitation introduced here

Every institution in this cluster resolved to the same coordinate — Tübingen's city centroid.
Within-city precision is therefore zero, which is harmless for a city this size but would
distort the neighbour-count measure in Paris or London, where campuses are tens of kilometres
apart. Street-level geocoding is needed before those cities are published.
