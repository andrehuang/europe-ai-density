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

P0 (schema and rules) in progress. Nothing has been verified yet — no number in this repo
should be quoted until `data/people.csv` has rows with `status = verified`.

## Method documentation

See [METHODOLOGY.md](METHODOLOGY.md) for the full inclusion protocol, source hierarchy, and
known limitations.
