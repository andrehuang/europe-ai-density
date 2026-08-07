# Directory-roster agent contract

Every institution roster is collected under this contract. It is a file rather than a
prompt written afresh each time, because improvising the instructions is how bias gets in:
enumerating five MPI-INF departments silently dropped the sixth, and omitting one sentence
about unresolved cases silently dropped seven people at Stuttgart.

Each rule below exists because its absence cost something real.

## What to collect

**Over-collect. Never filter by topic.** Record everyone whose title indicates an
independent position, whatever their research area. The project applies a
publication-based AI filter afterwards, and it works: of 78 people scraped from LISN, 8
survived it. A directory pass that pre-filters by topic loses people whose AI work is not
visible in a job title, and that loss is invisible downstream.

**AI faculty are not confined to the computer science department.** At LMU Munich, 18 of
43 qualifying people sit in the Institute of Statistics rather than Informatics, and a
computer-science-only sweep would have missed most of the university's machine-learning
chairs. Check statistics, mathematics, electrical engineering, cognitive science and the
medical faculty wherever the institution has them.

**Never enumerate the sub-units to visit.** Ask for the institution's own structure and
work through all of it. Naming "D1, D2, D4, D5, D6" caused an agent to skip D3 exactly as
instructed.

**Include**: professors of every rank, directors, department heads, independent and junior
research group leaders, tenure-track faculty, named fellowship holders running a group.
**Exclude**: postdocs, doctoral students, research staff inside somebody else's group,
emeritus, honorary/visiting/adjunct-only titles, administrative and technical staff.

## What never to decide

**Do not judge whether a title qualifies.** Record it verbatim, in the original language.
`data/titles.csv` makes that ruling once, per country, so the rule cannot drift with
whichever model did the scraping.

**Do not resolve entity ambiguity — report it and stop.** The ELLIS Institute Tübingen and
the ELLIS Unit Tübingen are different organisations sharing a name; one employs people and
the other does not. `data/institution_directory_urls.csv` pins the intended entity and
names the one it must not be confused with. If the page in front of you describes a
different organisation, say so rather than proceeding.

## Every person gets a row

**A low-confidence row beats a missing row.** If identity, position or currency cannot be
established, still write the row, set `confidence=low`, and say in `notes` what is missing.
An unresolved case must become an open question in the data, never a silent gap — a gap
appears downstream as "this city is small" and cannot be traced back.

This applies to running out of budget too. Seven Stuttgart candidates were dropped because
a search quota ran out mid-task; had they been written as low-confidence rows, the loss
would have been visible immediately.

## Multi-site institutions

Where `data/institution_sites.csv` marks an institution `requires_person_site`, the site
column is the most important field in the task, because sites count toward different
cities. MPI-SWS splits 13 Saarbrücken / 11 Kaiserslautern; assigning everyone to the
registered address would have moved eleven PIs into the wrong city.

Establish the site from evidence, and say which evidence. Physical addresses and building
codes have proved reliable. Phone area codes have not — one agent found them contradicting
the stated addresses and discarded them, which was correct. Mark `unclear` honestly rather
than guessing; a person marked unclear is held out, and a second single-site roster often
resolves them later.

## Second affiliations

Record every other institution the page names. Joint appointments are the norm, not the
exception: 12 of 16 DFKI Saarbrücken department heads hold a Saarland chair, 8 of 49 CISPA
faculty do, and 11 of 22 MPI-INF group leaders do. The project counts each person once, and
it can only do that if the overlaps are visible.

## Fetching

Fetch known URLs directly. **WebSearch is a fallback with a session cap of roughly 200
queries**, and four agents have exhausted it mid-task. Some sites sit behind bot protection
— dfki.de returns 403 to a direct fetch — and a reader proxy is an acceptable workaround.

Read the local-language pages. English pages at European institutions are often stale
summaries; German, French and Italian pages carry the current titles. The authoritative
document is frequently not a web page at all: LISN's official organigramme, a PDF dated
2025-09-01, listed eleven permanent researchers absent from the online directory.

## Output

Write the CSV to the path given in the task, with the header given in the task, then write
`sources.txt` listing every URL fetched with the retrieval date.

**Write the files before replying.** One agent spent 51k tokens, reported success and wrote
nothing; the orchestrator now verifies the artefact rather than the completion signal, but
an agent that writes first cannot fail that way.

Reply in at most five lines: row count, the site or affiliation breakdown, which URLs proved
most complete, roughly how many WebSearch calls were used, and anything that blocked you.
Never list the people in the reply — the roster belongs in the file, and repeating it costs
the orchestrator's context for nothing.
