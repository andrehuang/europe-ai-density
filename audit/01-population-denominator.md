# Population denominator audit

Two independent 1 km population grids were built. Both are reproducible from
`scripts/build_population_grid.py` and `scripts/build_ghs_grid.py`.

| | Eurostat census grid | GHS-POP |
| --- | --- | --- |
| Source | Eurostat 2021 census grid v1.0, retrieved 2026-08-06 | GHS-POP R2023A, epoch 2025, 30 arc-second |
| Basis | Census returns | Modelled from census units and built-up surface |
| Projection | ETRS89-LAEA (EPSG:3035), 1 km | WGS84 (EPSG:4326), 30 arc-second |
| Populated cells | 1,859,463 | 6,813,274 (window) |
| Role | Cross-check | **Primary denominator** |

## Finding 1 — the census grid has no United Kingdom

The Eurostat 2021 census grid returns **zero cells** for London, Edinburgh, and Cambridge.
The UK left the EU before the 2021 census round and does not appear. Iceland is likewise
absent.

The UK holds the largest national share of core-active AI faculty in this project, so a
UK-shaped hole in the denominator would make the ranking unpublishable. This is why GHS-POP,
despite being modelled rather than measured, is the primary denominator: one consistent
methodology across all 31 countries beats a more accurate source that covers 29 of them.

Switzerland and Norway *are* present in the census grid — EFTA participates in the European
census programme — so the cross-check covers most of the continent.

## Finding 2 — the two grids agree to within about 3%

Totals inside a ±0.5° box around each city centre:

| City | GHS-POP | Census grid | Difference |
| --- | --- | --- | --- |
| Paris | 12,572,087 | 12,580,732 | −0.1% |
| Warsaw | 3,871,967 | 3,806,676 | +1.7% |
| Munich | 4,578,174 | 4,464,643 | +2.5% |
| Athens | 3,833,974 | 3,938,619 | −2.7% |
| Milan | 8,570,564 | 8,328,051 | +2.9% |
| Berlin | 5,037,188 | 5,199,244 | −3.1% |
| Madrid | 7,946,384 | 7,229,577 | **+9.9%** |
| London | 16,514,780 | — | not covered |

Agreement is within ±3% everywhere except Madrid, where GHS-POP is ~10% higher. Density
figures should be read as carrying roughly a 3% denominator uncertainty, and Madrid's as
carrying 10%.

This agreement also validates both coordinate implementations independently: the hand-written
inverse LAEA in `build_population_grid.py` and the tag-derived affine transform in
`build_ghs_grid.py` were developed separately and land on the same ground.

## Finding 3 — GHS-POP has implausible hot cells

The densest cells in the extraction window hold 152,061 people in roughly 0.65 km², which is
about 234,000 people per km² — physically impossible. They cluster near Gemlik on the Sea of
Marmara, in Turkey, which is outside our scope. By contrast the census grid's densest cell
holds 56,158 people, in the Barcelona Eixample, which is plausible for the densest urban
fabric in Europe.

This is the known GHS-POP failure mode where a large census unit is redistributed onto a small
built-up footprint. It does not affect the ranking, since the artefacts observed are outside
scope, but any city-level figure should be spot-checked against the census grid where coverage
allows.

## Validation trail

The projection work was caught twice by sanity checks rather than by inspection, which is
worth recording:

1. Assuming GHS-POP sat on a clean global (−180, 90) origin produced London at 628k people.
   The raster's actual tiepoint is (−180.007916, 89.099583), a shift of nearly a degree of
   latitude. The transform is now read from `ModelTiepointTag` and `ModelPixelScaleTag` rather
   than assumed.
2. The inverse LAEA was validated by confirming the projection origin round-trips to exactly
   (52.000000, 10.000000), and that the most populated census cells land on the Barcelona
   Eixample and central Paris.

Independent agreement between the two pipelines is the strongest evidence that both are right.
