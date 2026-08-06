# Methodology

## 1. The question

For each place in Europe, how many **independent academic AI principal investigators** work
there, and how dense is that concentration relative to the population and area of the same
piece of ground?

We count people. We do not count papers, citations, funding, or students. A ranking of
output would reward large groups; this one asks how many *independent research agendas* a
place hosts.

**Snapshot date**: 2026-08-01. A person counts if they held a qualifying position on that
date. Positions that started or ended after it are recorded but not counted.

**Activity window**: 2021-01-01 to the snapshot date, so five full years plus a partial 2026.
The window is deliberately generous. Title verification is the binding constraint on who
counts; the publication filter only removes people with no recent AI activity at all, and
excluding a genuine PI costs more than admitting a marginal one.

## 2. Who counts

A person enters the roster when all four conditions hold.

**(a) Independent principal investigator.** They lead their own research agenda: they can
recruit and supervise doctoral students under their own name, and they hold their own
funding or a permanent group. `data/titles.csv` maps every academic title in scope, by
country, to a yes/no ruling, so the judgment is made once per title rather than once per
person. Cases the table cannot resolve go to `audit/<city>.md` with the reasoning written out.

**(b) Academic or non-profit sector.** Universities and public research institutes (MPI,
Inria, CNRS, ISTA, CWI, FBK, IIT, CSIC, SZTAKI, INSAIT, and similar). Corporate labs are
tracked in a separate table and never enter the main ranking, even for researchers holding a
courtesy academic title. Applied-contract institutes without doctoral supervision (Fraunhofer,
TNO) are excluded unless the person also holds a university chair.

**(c) Core AI.** At least one authored paper at a core-layer venue in `data/venues.csv`
within the activity window, in any author position. Machine learning, computer vision, natural
language processing, reinforcement learning, robotics, speech, and learning theory make up
the core layer. AI4Science, computational neuroscience, medical imaging, and AI-adjacent HCI
form an extended layer that the site can switch on.

**(d) Located in scope.** Primary appointment in the EU-27, EFTA (CH, NO, IS, LI), or the UK.

Anyone considered and rejected gets a row in `data/exclusions.csv` with one of the codes in
`data/exclusion_codes.csv`, plus the source that settled it. The exclusion file is part of the
deliverable: a reader who disagrees with the ranking should be able to find the specific
person they think is missing and see why.

## 3. Finding candidates

CSRankings alone under-counts by construction, because it lists only faculty who can
supervise CS doctoral students at a listed university. That rule drops the directors and
group leaders at MPI, Inria, ISTA, and CWI — precisely the institutions that concentrate
European AI. ELLIS rosters fill some of that gap but introduce a different bias: a city
without an ELLIS unit looks empty even when it is not.

We therefore take the union of five independent recall sources and adjudicate person by
person:

| Source | What it contributes | Known bias |
| --- | --- | --- |
| OpenAlex (by institution ROR + core venue + window) | Widest recall, covers non-university institutes | Author disambiguation errors; returns doctoral students |
| DBLP affiliation notes | Clean publication records, stable person keys | Affiliation notes are sparse and often stale |
| CSRankings faculty files | Human-curated, verified supervision rights | University CS departments only |
| ELLIS unit and society rosters | Research-institute PIs, cross-checks seniority | Absent for cities with no unit; membership ≠ position |
| Institutional faculty directories | Authoritative on current title | Manual, brittle, requires a dated snapshot |

Recall is measured, not assumed: for a random sample of institutions we hand-build a complete
roster from the department page and report what fraction each automated source recovered.

## 4. Adjudicating each candidate

Each candidate passes through a fixed sequence, and the outcome of each step is stored:

1. Resolve identity — ORCID and DBLP key, merging duplicates under one `person_id`.
2. Read the current title from an institutional page; store the URL and retrieval date, and
   snapshot the HTML into `data/raw/`.
3. Apply `data/titles.csv` to get the PI ruling and default tier.
4. Verify ≥1 core-venue paper in the activity window against DBLP.
5. Record every affiliation, not only the primary one.
6. Assign a tier, or write an exclusion row.

A person with `status = verified` has all six steps complete. Numbers should not be quoted
from rows in any other state.

## 5. Cross-appointments

Cross-appointed people are the most common way a ranking silently inflates. Each person
appears exactly once in `data/people.csv`, with `primary_affiliation` and a
semicolon-separated `secondary_affiliations` list. The site offers three attribution modes:

- **Primary only** (default) — the person counts at their primary institution.
- **Split evenly** — a person with *n* qualifying affiliations contributes 1/*n* to each.
- **Count everywhere** — full weight at every location.

Every ranking figure states which mode produced it. Because the roster stores affiliations
rather than pre-aggregated counts, switching modes rebuilds the ranking from the same rows.

## 6. Geography

### From institutions to cities

Cities are derived, not chosen. Each verified person is geocoded to the street address of
their primary institution. Locations are then clustered spatially, and any cluster with at
least five verified PIs enters the ranking under the name of its dominant settlement. This
avoids the selection bias of a hand-picked city list, where a missing city is
indistinguishable from an empty one.

Clusters are reported both at a tight radius (a single campus or town, ~10 km) and at a
commuting radius (~40 km), because Tübingen–Stuttgart, Paris–Saclay, Zürich–Lausanne, and
Delft–Rotterdam–Leiden are legitimately readable either way. The map lets a reader draw the
boundary themselves.

### The denominator

Administrative population figures are unusable as a primary denominator. Tübingen city holds
90k people, Paris *intra-muros* 2.1M, and Île-de-France 12M; each is a defensible "city
population" and each produces a different winner. Rather than defend one choice, we remove
the choice: population comes from a **1 km population grid**, summed over whatever geometry
the reader has selected, so numerator and denominator always describe the same ground.

Which grid took a decision. The Eurostat 2021 census grid is the more accurate source, being
built from actual census returns, but it **excludes the United Kingdom and Iceland** — the UK
having left the EU before the 2021 census round. Since the UK holds the largest single
national share of European AI faculty, a UK-shaped hole in the denominator is disqualifying.

The primary denominator is therefore **GHS-POP R2023A, epoch 2025, 30 arc-second**, which
covers every country in scope on one consistent methodology. Consistency matters more than
per-country precision here, because the output is a cross-country comparison: a denominator
that is uniformly modelled beats one that is census-accurate in 25 countries and absent in
two.

The Eurostat census grid is retained as an independent cross-check wherever it has coverage,
and the per-city discrepancy between the two is reported. That turns the choice of
denominator from a hidden assumption into a published error bar.

Administrative figures still appear in `data/cities.csv` — with source, year, boundary
definition, and a note on how badly that boundary fits the actual research cluster — so
readers can compare against conventional statistics.

## 7. Density measures

| Measure | Definition | Reads as |
| --- | --- | --- |
| Count | Verified PIs in the selected region | Scale |
| Per 100k | Count ÷ (grid population in region) × 100,000 | Conventional density |
| Per km² built-up | Count ÷ built-up area in region (GHS-BUILT) | Spatial concentration |
| Median neighbour count | For each PI, the number of other PIs within 10 km; the region's median | What a typical PI experiences |

The last measure exists because per-capita density is an artifact of how much farmland a
boundary encloses, while the number of colleagues within cycling distance is not. It is the
measure closest to the lived question of whether a place feels like an AI hub.

The headline plot is count against grid population on log-log axes, with iso-density
diagonals. One figure then carries both facts a reader needs: Tübingen sits high above the
diagonal at small scale, London sits far right at low density, and neither is collapsed into
a single rank.

## 8. Tiers and sensitivity

Contested inclusions are exposed rather than argued. Every person carries a tier (T1, T2, T3,
X, or C — see the README), and the site lets a reader toggle each layer and watch the ranking
move.

The rule governing T3 matters most. A local AI-center roster will always surface people the
general rules miss — the Tübingen AI Center is the motivating example — but auditing one city
that way while leaving the others unaudited tilts the comparison toward the audited city.
T3 is therefore applied to every city or to none, and the site marks the layer as incomplete
until coverage is uniform.

## 9. Reproducibility

Every source snapshot in `data/raw/` carries its URL and retrieval date and is never
overwritten. `scripts/` rebuilds the entire site from `data/` with no manual steps, and a
link-checker re-validates every evidence URL, reporting rot rather than silently dropping it.
Each release is tagged with its snapshot date so a number quoted from the site can be traced
to the roster version that produced it.

## 10. Known limitations

**Title mapping compresses real differences.** A French CR and a German W1 both count as
independent PIs, and both rulings are contestable. The ruling is at least explicit and
applied uniformly, and `data/titles.csv` can be forked and re-run.

**Recall is not provable.** We can measure how much of a hand-built roster the automated
sources recover, but not how many PIs no source lists. Small institutions and non-English
departmental pages are where coverage is weakest.

**Publication filters penalise theory and robotics.** A researcher publishing mainly in
journals or at venues outside the core list can fail condition (c) despite an active AI
agenda. The extended layer partly compensates.

**Geocoding to an institutional address misplaces distributed institutions.** Universities
with several campuses are assigned to the department address, which the per-city audit notes
where it matters.

**The snapshot ages immediately.** European faculty move constantly, so the ranking describes
2026-08-01 and nothing else.

**2026 is only partially indexed.** The activity window runs into an incomplete year: NeurIPS
2026 has not happened, and DBLP lags several months behind conferences that have. Anyone whose
only qualifying paper would be a 2026 one may be missed, which biases against researchers who
started recently.
