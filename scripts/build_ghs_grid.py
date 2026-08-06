#!/usr/bin/env python3
"""Extract the European window of GHS-POP and store it as populated cells.

GHS-POP R2023A epoch 2025 at 30 arc-seconds is the primary denominator: unlike the
Eurostat census grid it covers every country in scope, including the UK and Iceland,
on a single consistent methodology. See METHODOLOGY.md section 6.

The source is a 43200x21600 global GeoTIFF, so the European window is read lazily
rather than materialising 3.7 GB.

Run with the project venv: .venv/bin/python scripts/build_ghs_grid.py
Output: data/derived/ghspop_30ss_europe.npz with lat, lon, pop.
"""

import pathlib
import sys

import numpy as np
import tifffile

ROOT = pathlib.Path(__file__).resolve().parent.parent
GHS_DIR = ROOT / "data" / "raw" / "grid" / "ghs"
OUT = ROOT / "data" / "derived" / "ghspop_30ss_europe.npz"

LON_MIN, LON_MAX = -32.0, 45.0
LAT_MIN, LAT_MAX = 34.0, 72.0


def main() -> int:
    tifs = sorted(GHS_DIR.glob("*.tif"))
    if not tifs:
        print(f"no GeoTIFF under {GHS_DIR} — unzip the download first", file=sys.stderr)
        return 1
    src = tifs[0]
    print(f"source: {src.name}")

    with tifffile.TiffFile(src) as tf:
        page = tf.pages[0]
        print(f"full raster: {page.shape} dtype={page.dtype}")
        # Read the georeferencing from the file rather than assuming a clean global
        # extent: this raster's tiepoint is (-180.0079, 89.0996), and assuming
        # (-180, 90) shifts every row by about a degree of latitude.
        sx, sy, _ = page.tags["ModelPixelScaleTag"].value
        _, _, _, lon_origin, lat_origin, _ = page.tags["ModelTiepointTag"].value
        print(f"pixel scale: {sx:.10f} deg | origin: ({lon_origin:.6f}, {lat_origin:.6f})")

        col0 = max(int((LON_MIN - lon_origin) / sx), 0)
        col1 = min(int((LON_MAX - lon_origin) / sx) + 1, page.shape[1])
        row0 = max(int((lat_origin - LAT_MAX) / sy), 0)
        row1 = min(int((lat_origin - LAT_MIN) / sy) + 1, page.shape[0])

        store = tf.aszarr()
        import zarr

        arr = zarr.open(store, mode="r")
        window = np.asarray(arr[row0:row1, col0:col1], dtype=np.float32)
    print(f"europe window: rows {row0}:{row1} cols {col0}:{col1} -> {window.shape}")

    # GHS-POP marks no-data with a negative sentinel; real cells are >= 0.
    rows, cols = np.nonzero(window > 0)
    pop = window[rows, cols]
    lat = (lat_origin - (row0 + rows + 0.5) * sy).astype(np.float32)
    lon = (lon_origin + (col0 + cols + 0.5) * sx).astype(np.float32)

    np.savez_compressed(OUT, lat=lat, lon=lon, pop=pop)
    print(f"populated cells: {len(pop)}")
    print(f"total population in window: {pop.sum():,.0f}")

    print("\nmost populated cells (projection sanity check):")
    for i in np.argsort(-pop)[:8]:
        print(f"  {pop[i]:9,.0f}  ({lat[i]:.4f}, {lon[i]:.4f})")

    print("\ncoverage probe:")
    for name, la, lo in [
        ("London", 51.507, -0.128), ("Edinburgh", 55.953, -3.188),
        ("Reykjavik", 64.146, -21.94), ("Paris", 48.857, 2.352),
        ("Tübingen", 48.521, 9.058), ("Zurich", 47.377, 8.540),
    ]:
        m = (np.abs(lat - la) < 0.25) & (np.abs(lon - lo) < 0.4)
        print(f"  {name:12s} cells={int(m.sum()):6d}  pop={pop[m].sum():12,.0f}")

    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
