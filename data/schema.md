# Data schemas

## `people.csv` — one row per person, the primary artifact

| Column | Type | Description |
| --- | --- | --- |
| `person_id` | string | Stable slug, `surname-givenname-NN`. Never reused, never renumbered. |
| `full_name` | string | As written on the institutional page, with diacritics. |
| `orcid` | string | ORCID iD, blank if none found. |
| `dblp_key` | string | DBLP person key, e.g. `homepages/12/3456`. |
| `openalex_id` | string | OpenAlex author ID. |
| `primary_affiliation` | string | `inst_id` from `institutions.csv`. |
| `secondary_affiliations` | string | Semicolon-separated `inst_id` list. Empty for most people. |
| `title_local` | string | Title verbatim in the local language. |
| `title_key` | string | Join key into `titles.csv` (`country` + `title_local`). |
| `appointment_start` | date | Year-month if known; used to apply the snapshot date. |
| `appointment_end` | date | For fixed-term posts. Blank if permanent. |
| `fte_primary` | float | Fraction of appointment at the primary institution. Default 1.0. |
| `tier` | enum | `T1`, `T2`, `T3`, `X`, or `C`. |
| `field_layer` | enum | `core` or `extended`. |
| `core_venue_papers_window` | int | Count of core-layer venue papers in the activity window (2021-01-01 to 2026-08-01), from DBLP. |
| `evidence_url` | string | Institutional page establishing the current title. |
| `evidence_retrieved` | date | ISO date the URL was fetched. |
| `evidence_snapshot` | string | Path under `data/raw/`. |
| `recall_sources` | string | Semicolon-separated: `openalex`, `dblp`, `csrankings`, `ellis`, `directory`. |
| `status` | enum | `verified`, `pending`, `disputed`. |
| `notes` | string | Free text. Anything contested goes here and in `audit/<city>.md`. |

A row counts toward a published number only when `status = verified`.

## `institutions.csv`

| Column | Description |
| --- | --- |
| `inst_id` | Stable slug, e.g. `de-mpi-is`, `ch-ethz`. |
| `name_en` / `name_local` | Institution names. |
| `country` | ISO 3166-1 alpha-2. |
| `city` | Settlement of the relevant department, not the legal seat. |
| `type` | `university`, `research_institute`, `corporate`. |
| `ror_id` | ROR identifier, filled from the ROR API. |
| `lat` / `lon` | Geocoded department address. |
| `address` | Street address used for geocoding. |
| `csrankings_name` | Matching CSRankings affiliation string, if any. |
| `ellis_unit` | `yes` / `no`. |
| `in_scope` | `yes` / `no`, with the reason in `notes`. |

## `cities.csv` — administrative comparison only

Not used for the primary density figures. Included so readers can compare against
conventional statistics and see where the boundary fits badly.

| Column | Description |
| --- | --- |
| `city_id`, `name`, `country` | Identity. |
| `admin_population` | Population under the stated definition. |
| `admin_definition` | `municipality`, `LAU`, `FUA`, `NUTS3`, or `metro`. |
| `population_year` | Reference year. |
| `population_source` | Full citation with URL. |
| `area_km2` | Area under the same definition. |
| `boundary_risk` | `low` / `medium` / `high`. |
| `boundary_note` | How the administrative boundary misfits the research cluster. |

`boundary_risk = high` applies where the municipal boundary and the research cluster diverge
badly — Paris (cluster spans Saclay, 20 km outside the city), Tübingen (MPI-IS spans Tübingen
and Stuttgart), Vienna (ISTA sits in Klosterneuburg, outside the city), Barcelona (UAB/CVC and
IIIA sit in Cerdanyola, outside the municipality).

## `exclusions.csv`

| Column | Description |
| --- | --- |
| `candidate_name` | Name as encountered. |
| `institution` | `inst_id` or free text. |
| `reason_code` | Join key into `exclusion_codes.csv`. |
| `evidence_url`, `evidence_retrieved` | Source that settled it. |
| `notes` | Free text, required for `E13 unverifiable` and `E15 non_independent`. |
