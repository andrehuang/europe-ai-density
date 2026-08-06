# Quality assurance without a local expert per city

The obvious objection to this project is that its owner can check Tübingen carefully because
they know Tübingen, and cannot do that for forty cities. Local knowledge catches things no
general rule does: that the ELLIS Institute and the ELLIS Unit are different organisations,
that MPI for Intelligent Systems runs two campuses in two cities, that a name on a page left
three years ago.

The answer is not to claim the pipeline has local knowledge. It is to replace the parts of
local knowledge that can be externalised, measure what remains, and publish the residual as a
declared uncertainty. Six mechanisms, in descending order of strength.

## 1. Two recall modalities with uncorrelated failure modes, and a forced reconciliation

Institution pages and publication records fail in opposite directions.

An institution page under-reports: the MPI-IS directory pass omitted Michael Black and Moritz
Hardt, both directors there. It does not, however, invent people who left.

A publication record over-reports: DBLP's affiliation notes return Kun Zhang (now CMU),
Jan Peters (Darmstadt), Stefanie Jegelka (TU Munich) and Suvrit Sra (TU Munich) for Tübingen.
It does not, however, lose an active researcher because a web page was hard to parse.

Running both and reconciling them converts an unanswerable question into a finite list.
Tübingen, at the ≥3 threshold:

| Modality | People |
| --- | --- |
| Roster-driven (institution directories + CSRankings) | 45 |
| Publication-driven (DBLP current affiliation) | 57 |
| Overlap | 20 |
| Union | 82 |

Thirty-seven names appear only in the publication pass and thirty-seven only in the roster
pass. Every one of them needs a disposition — left, postdoc, doctoral student, genuinely
missed — recorded in `data/exclusions.csv`. "Did we miss anyone?" is unanswerable. "Here are
the 37 candidates we considered and why each was excluded" is answerable, and it is bounded.

**Gate**: no city enters the main ranking before its reconciliation is complete.

## 2. Source redundancy, published as a confidence grade

Of the 45 people in the merged Tübingen roster, **20 were found by exactly one source** — and
Tübingen has four overlapping directory sources plus CSRankings. Michael Black appears only
via ELLIS; Kerstin Ritter and Georg Martius only via the Tübingen AI Center.

A city served by a single institution has no such redundancy, and its roster cannot be trusted
to the same degree. That difference is measurable and must be shown rather than smoothed over.

**Gate**: fewer than two independent sources means the city is published with a low-confidence
flag, or held out of the main ranking entirely.

## 3. National registries replace local knowledge where they exist

Some countries maintain an authoritative public register of academic staff. Where one exists
it is more reliable than any institution page, and the usual relationship inverts: the register
becomes the primary roster and institution pages become the cross-check.

| Country | Authoritative source | Coverage |
| --- | --- | --- |
| Italy | CINECA / MUR public register of professors | Complete, all ranks |
| France | Laboratory *organigrammes*, HAL, Inria RADAR activity reports | Per-laboratory, dated |
| Germany | GEPRIS (DFG project PIs) | Partial; funded projects only |
| Spain, UK, Netherlands | none central | Institution pages only |

The LISN run demonstrated the principle by accident. The Sonnet pass found the laboratory's
official organigramme PDF dated 2025-09-01, which lists every team's permanent researchers,
surfaced eleven people absent from the online directory entirely — Michèle Sebag among them —
and settled that Alexandre Allauzen had left for ESPCI in 2019.

The lesson generalises: **local knowledge usually exists as a document.** "Find the official
register" is a behaviour that can be written into the agent contract; it is not innate
expertise.

## 4. Entities pinned in data, ambiguity escalated rather than resolved

Given both URLs, a pilot agent scraped the ELLIS *Unit* Tübingen — a network node whose twelve
members all hold their primary posts elsewhere — instead of the ELLIS *Institute*, an
independent employer founded in 2023 with fourteen of its own group leaders. Counting the
first as an employer double-counts; missing the second loses fourteen people including
Frank Hutter and Kashyap Chitta.

This is an entity-resolution failure, not a capability failure, and the fix belongs in data.
`data/institution_directory_urls.csv` pins each institution to a `directory_url` and names the
entity it must not be confused with. The same file records that MPI-IS and MPI-SWS need
campus filtering, that inria.fr's team listings return 403, and that the Alan Turing Institute
seconds its fellows from other universities and can never be a headcount source.

Agents are instructed to **report** entity ambiguity and stop, not to resolve it.

## 5. Read the local language

European institutions' English pages are frequently stale summaries of the local-language
pages. Directory agents must work in German, French, Italian, Spanish, Dutch, Polish and the
Nordic languages rather than defaulting to the English version.

## 6. A public correction path

CSRankings itself is maintained by crowdsourced corrections through pull requests. That is the
honest scaling answer here too: the project cannot buy local expertise for forty cities, but it
can make each city checkable by the people who have it. That is why per-person auditability —
one row, one title, one evidence URL, one retrieval date — was the design goal from the first
commit rather than a reporting nicety.

## Model tiering, measured

Directory reading splits into two tasks that need different models.

| Institution | Model | Tokens | People | Active (≥3) | Verdict |
| --- | --- | --- | --- | --- | --- |
| Tübingen AI Center (one people page) | Haiku | 27k | 32 | 25 | Adequate |
| MPI-IS Tübingen (many group pages) | Haiku | 61k | 20 | 17 | Missed two directors |
| LISN (19 teams, 425 directory entries) | Haiku | 42k | 78 | 8 | Missed 100 of 156 |
| LISN, same contract | Sonnet | 238k | 156 | 17 | Found the official organigramme |
| ELLIS Institute Tübingen | Sonnet | 133k | 14 | 14 | Detected a stale "Alumni" record |

Haiku is adequate for a single flat directory page and unreliable for a multi-team laboratory,
where it under-recalls by roughly half. Sonnet costs about five times more and repays it by
locating authoritative documents and noticing contradictions between pages.

**Rule**: Haiku for institutions with one directory page and fewer than about thirty people;
Sonnet for multi-team laboratories, research institutes, and any institution where the two
recall modalities disagree by more than 20%.

## Orchestration reliability is a separate failure mode

An adjudication agent spent 51k tokens across 31 tool calls, reported completion, and wrote
no file at all — its closing message was an unrelated sentence about waiting for a
notification. Nothing in the completion signal distinguished this from success.

At the scale this project needs, silent no-output runs would appear as cities with
implausibly small rosters, and the cause would be invisible in the data. Two rules follow:

- **Verify the artefact, never the completion signal.** Every agent's expected output path is
  checked for existence and row count before its result is believed.
- **A blank row beats a missing row.** Agents are told to write a row with `confidence=low`
  and a note for anyone they could not establish, so an unresolved case becomes an explicit
  open question in the data rather than a silent gap.

Recovery is cheap when it happens: resuming the same agent to write down what it already
found costs far less than repeating its research.

## What this does not fix

A researcher at a small institution, publishing outside the venue list, with no web presence,
will be missed. No mechanism here finds that person. It is a stated limitation of the ranking,
not a defect to be engineered away.

Capture-recapture estimation was considered for putting a number on total coverage. For
Tübingen it returns 128 against a union of 82. The two modalities are not independent and the
publication pool is contaminated with people who have left, so both assumptions of the
Lincoln-Petersen estimator are violated. It is reported here as a diagnostic that the sources
disagree substantially, and deliberately not presented as a population estimate.
