# Europe AI Density

A per-person auditable ranking of **academic AI talent density** across Europe (EU + EFTA + UK).

This project counts **people, not papers**. It asks a single question: *if you are an AI
researcher, where in Europe are you surrounded by the most independent AI principal
investigators?*

## What makes this different

Most "AI hub" rankings are unfalsifiable — they report a number per city with no way to
ask *which people*. Here, every claim decomposes to a named row:

- **Every included person** has a row in `data/people.csv` with a title, an evidence URL,
  and a retrieval date.
- **Every excluded person** has a row in `data/exclusions.csv` with a reason code and a source.
- **Every judgment call** about what counts as a PI is written down once, per country, in
  `data/titles.csv` — not decided ad hoc per person.
- **Cross-appointed people** appear exactly once, with all their affiliations listed. Three
  attribution modes (primary-only / split evenly / count everywhere) are switchable in the UI.
  Nobody is silently double-counted.

## Core design decisions

### 1. The denominator shares geometry with the numerator

Administrative city boundaries are the single largest source of manipulation in density
rankings: Tübingen city is 90k people, Paris *intra-muros* is 2.1M, Île-de-France is 12M.
Picking any of them is a thumb on the scale.

Instead we use a **1 km population grid** (Eurostat GEOSTAT 2021, cross-checked against
GHS-POP). Draw any region on the map and both the PI count and the population are summed
over the *same* geometry. Administrative figures are kept only as a comparison table in
`data/cities.csv`, with their boundary-mismatch risk noted per city.

### 2. Cities are an output, not an input

We enumerate *institutions* (a closed, checkable set), verify people, geocode them, then let
cities emerge by spatial clustering. Any cluster with ≥5 verified PIs enters the ranking.
No hand-picked city list, so no city can be missing because nobody thought of it.

### 3. Contested inclusions are a UI switch, not a footnote

Each person carries a tier:

| Tier | Meaning |
| --- | --- |
| **T1** | On a university faculty roster, CSRankings-listed, ≥1 core-AI venue paper in the activity window |
| **T2** | Research-institute PI or group leader (MPI, Inria, ISTA, CWI, FBK, IIT, …), position manually verified |
| **T3** | Local AI-center / cluster supplement — applied uniformly to *every* city or not at all |
| **X** | Extended-field layer (AI4Science, computational neuroscience, medical imaging) |
| **C** | Corporate lab — excluded from the main ranking, shown as a separate table and map layer |

The default ranking is **T1 + T2**. Everything else is a toggle, so a reader can see exactly
how much a contested rule changes the outcome instead of taking our word for it.

### 4. Four density measures, because "density" is genuinely ambiguous

| Measure | Question it answers |
| --- | --- |
| Absolute count | How big is the cluster? |
| Per 100k residents (grid population in the selected region) | Classic density |
| Per km² of built-up area | Spatial concentration |
| **Median neighbour count** — for each PI, how many other PIs are within 10 km; take the city median | *What a typical PI actually experiences* |

The last one is the closest to lived experience and is immune to how much farmland a city's
administrative boundary happens to enclose.

## Scope

- **Geography**: EU-27 + EFTA (CH, NO, IS, LI) + UK. Turkey, Israel, Russia, Ukraine and the
  Western Balkans appear only in an appendix table, never in the main ranking.
- **Field**: core AI (ML, CV, NLP, RL, robotics, speech, AI theory) for the main ranking;
  extended fields as a switchable tier.
- **Sector**: academic and non-profit research institutes. Corporate labs are tracked
  separately and never enter the main ranking.
- **Snapshot date**: 2026-08-01 — a person counts if they held a qualifying position then.
- **Activity window**: 2021-01-01 to the snapshot date.

## Repository layout

```
data/raw/              Immutable source snapshots, each with URL + retrieval date
data/people.csv        One row per person — the primary artifact
data/exclusions.csv    Every rejected candidate, with reason code and source
data/titles.csv        Country × academic title → independent-PI ruling
data/venues.csv        Venue list defining "core AI" and "extended"
data/institutions.csv  Institution registry (ROR, city, coordinates, type)
data/cities.csv        Administrative comparison figures + boundary risk notes
audit/<city>.md        Per-city audit log: who was added, who was cut, what was contested
scripts/               Recall, dedup, geocoding, grid aggregation, site build
site/                  Output: ranking table, scatter plot, interactive map
```

## Status

Live at **https://andrehuang.github.io/europe-ai-density/**

Seven cities have been through the full protocol: **244 people, all `status = verified`**
(146 T1, 77 T2, 21 T3), against **178 exclusions**, every one carrying a reason code and a
source URL. 3,372 decisions are recorded in `data/decisions.jsonl`.

| City | PIs | | City | PIs |
| --- | --- | --- | --- | --- |
| München | 90 | | Stuttgart | 20 |
| Saarbrücken | 38 | | Potsdam | 16 |
| Tübingen | 35 | | Kaiserslautern | 10 |
| Berlin | 35 | | | |

Potsdam is its own city rather than part of Berlin. It is 25–35 km from Mitte, and this
project places people where they work; whether the two combine is the reader's radius call.

**Every other city on the map is a CSRankings-only preview**, drawn hollow rather than
filled, and inherits every gap documented in `audit/00-source-coverage.md`. Those numbers
are not results. See [STATUS.md](STATUS.md) for what is trustworthy and what is not.

## Disputing a row

Every number here is an assertion about named people, so it has to be contestable. Open an
issue or a pull request against the relevant CSV — there is no private correction channel,
because a correction nobody can see is not an audit.

**What settles a disagreement** is the source, not the argument. The hierarchy is fixed:

1. The institution's own dated directory page — first-party, settles it.
2. CSRankings — curated, but second-hand.
3. A DBLP affiliation note — undated and crowd-maintained. It is grounds for a re-check,
   never evidence that overrides 1.

So the useful form of a dispute is a link of type 1, with the date you retrieved it.

**What an exclusion does and does not mean.** `data/exclusions.csv` records that someone
falls outside *this count's scope rule* on the snapshot date — most often that the post is
not an independent one (`E15`), or that they had already moved (`E08`). It is a statement
about a boundary, not about a researcher's standing or quality, and the reason text is kept
in full precisely so you can judge whether the boundary was drawn correctly.

**The full history of any decision**, including reversals and what evidence caused them:

```
python3 scripts/decisionlog.py "<name>"      one person's complete decision history
python3 scripts/decisionlog.py --flips       every ruling that changed, and why
```

## Method documentation

See [METHODOLOGY.md](METHODOLOGY.md) for the full inclusion protocol, source hierarchy, and
known limitations.
