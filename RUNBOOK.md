# Runbook

Everything is a script. There are no manual steps, and no step depends on a file someone
edited by hand except the four registries listed below.

## Registries you edit by hand

| File | What it decides |
| --- | --- |
| `data/cities.csv` | Which cities exist, which rosters and CSRankings affiliations feed them, and how multi-site institutions split. **Adding a city means editing this file only.** |
| `data/titles.csv` | Whether a title counts as an independent PI, per country. |
| `data/institutions_supplement.csv` | Institutions CSRankings does not list. |
| `data/institution_ror_overrides.csv`, `data/institution_sites.csv`, `data/institution_directory_urls.csv` | Geocoding and entity pinning where the automatic match fails. |

`scripts/config.py` is the only thing that reads `data/cities.csv`, so the definition cannot
drift between scripts. It used to live in four of them, and two bugs came directly from
that: the payload applied adjudication rulings for Tübingen alone, and the city finaliser
raised KeyError for every city but Tübingen inside a loop that discarded stderr.

## Order

Steps 1–4 are one-off per snapshot and cost nothing but time. 5–9 are the per-city loop.

```
1  scripts/fetch_csrankings.py        CSRankings roster           (~1 min)
2  scripts/parse_dblp.py              DBLP dump -> venue papers, person index  (~15 min)
3  scripts/build_candidates.py        join, apply the AI filter
4  scripts/build_population_grid.py   Eurostat census grid   } either alone is enough;
   scripts/build_ghs_grid.py          GHS-POP, the primary   } both gives the error bar
   scripts/geocode_institutions.py    ROR: identity and city
   scripts/geocode_precise.py         Nominatim: campus precision

5  (agents)                           collect institution directories per AGENT_CONTRACT.md
6  scripts/check_rosters.py           resolve roster names against DBLP
7  scripts/apply_titles.py            rule on every title; unruled ones go to review
8  scripts/reconcile_city.py <slug>   queue what the two recall paths disagree about
9  (agents)                           settle the queue
   scripts/currency_check.py          OpenAlex: has anyone moved since the page was written
   scripts/apply_adjudications.py     fold the rulings back in, and log each one

   scripts/build_site_payload.py      counts, data/people.csv, data/exclusions.csv, payload
   scripts/build_site.py              assemble the single-file page
```

`build_site_payload.py` writes the primary artifacts *and* the site from one pass. They
used to come from two scripts; one rotted, and the number quoted in conversation came from
the survivor while `data/people.csv` sat stale and single-city.

## Checks worth running

```
python3 scripts/decisionlog.py --flips        people whose ruling changed, and why
python3 scripts/decisionlog.py "<name>"       one person's full decision history
python3 scripts/decisionlog.py --city <name>  a city's current decisions
```

Two invariants have each caught real defects and are worth re-checking after any change:

- **Two paths computing the same city must agree.** Every disagreement so far was a
  defect: alias duplicates, a homonym collapse that moved a TU Ilmenau physicist to
  Tübingen, a bare name matching the wrong DBLP person.
- **A status must be earned, not inferred from a file existing.** Berlin was briefly
  labelled "reconciled" because an empty rulings file had been written for it.

## Caching

Every fetcher caches under `data/raw/<source>/<snapshot>/` and **never caches an empty
response** — a throttled request and a genuine miss look identical, and caching the second
freezes a transient failure. 29% of one Nominatim run's cache turned out to be throttled
requests recorded as permanent misses.
