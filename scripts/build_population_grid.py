#!/usr/bin/env python3
"""Turn the Eurostat 2021 census grid into a numpy array of populated 1 km cells.

The grid ships as a 1.2 GB GeoPackage, but every cell's position is encoded in its
GRD_ID ("CRS3035RES1000mN2692000E4341000"), so the attribute table alone is enough —
sqlite3 reads it and no GIS stack is needed.

Coordinates are ETRS89-LAEA (EPSG:3035). The inverse projection to WGS84 is implemented
here directly (Snyder, oblique ellipsoidal Lambert azimuthal equal-area) so that the
pipeline has no binary geospatial dependency at all.

Output: data/derived/popgrid_1km.npz with easting, northing, lat, lon, pop.
"""

import pathlib
import sqlite3
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
GPKG = ROOT / "data" / "raw" / "grid" / "2026-08-06" / "ESTAT_Census_2021_V1-0.gpkg"
TABLE = "ESTAT_Census_2011_V1-0"  # the 2021 release kept the 2011 table name
OUT = ROOT / "data" / "derived" / "popgrid_1km.npz"

# EPSG:3035 — ETRS89 / LAEA Europe on GRS80.
A = 6378137.0
F = 1.0 / 298.257222101
E2 = 2 * F - F * F
E = np.sqrt(E2)
LAT0 = np.radians(52.0)
LON0 = np.radians(10.0)
X0, Y0 = 4321000.0, 3210000.0


def _q(phi):
    """Snyder's q: the authalic-latitude numerator."""
    s = np.sin(phi)
    return (1 - E2) * (
        s / (1 - E2 * s * s) - (1 / (2 * E)) * np.log((1 - E * s) / (1 + E * s))
    )


QP = _q(np.pi / 2)
RQ = A * np.sqrt(QP / 2)
BETA0 = np.arcsin(_q(LAT0) / QP)
D = (A * np.cos(LAT0) / np.sqrt(1 - E2 * np.sin(LAT0) ** 2)) / (RQ * np.cos(BETA0))


def laea_to_wgs84(x, y):
    """EPSG:3035 easting/northing -> (lat_deg, lon_deg)."""
    xp = (x - X0) / D
    yp = D * (y - Y0)
    rho = np.hypot(xp, yp)
    # A zero radius is the projection origin; avoid a divide and substitute it back.
    safe = np.where(rho == 0, 1.0, rho)
    c = 2 * np.arcsin(np.clip(rho / (2 * RQ), -1.0, 1.0))
    sin_c, cos_c = np.sin(c), np.cos(c)
    beta = np.arcsin(
        np.clip(cos_c * np.sin(BETA0) + (yp * sin_c * np.cos(BETA0)) / safe, -1.0, 1.0)
    )
    beta = np.where(rho == 0, BETA0, beta)
    lon = LON0 + np.arctan2(
        xp * sin_c,
        rho * cos_c * np.cos(BETA0) - yp * sin_c * np.sin(BETA0),
    )
    lon = np.where(rho == 0, LON0, lon)
    # Authalic latitude -> geodetic latitude (Snyder 3-12).
    e4, e6 = E2 * E2, E2 * E2 * E2
    lat = (
        beta
        + (E2 / 3 + 31 * e4 / 180 + 517 * e6 / 5040) * np.sin(2 * beta)
        + (23 * e4 / 360 + 251 * e6 / 3780) * np.sin(4 * beta)
        + (761 * e6 / 45360) * np.sin(6 * beta)
    )
    return np.degrees(lat), np.degrees(lon)


def main() -> int:
    if not GPKG.exists():
        print(f"missing grid: {GPKG}", file=sys.stderr)
        return 1

    con = sqlite3.connect(f"file:{GPKG}?mode=ro", uri=True)
    rows = con.execute(
        f'SELECT GRD_ID, OBS_VALUE_T FROM "{TABLE}" WHERE OBS_VALUE_T > 0'
    ).fetchall()
    con.close()
    print(f"populated cells: {len(rows)}")

    east = np.empty(len(rows), dtype=np.int32)
    north = np.empty(len(rows), dtype=np.int32)
    pop = np.empty(len(rows), dtype=np.float32)
    for i, (grd, value) in enumerate(rows):
        n_part, e_part = grd.split("N", 1)[1].split("E")
        north[i] = int(n_part)
        east[i] = int(e_part)
        pop[i] = value

    # GRD_ID names the lower-left corner; shift to the cell centre.
    lat, lon = laea_to_wgs84(east.astype(np.float64) + 500, north.astype(np.float64) + 500)

    np.savez_compressed(
        OUT, easting=east, northing=north, lat=lat.astype(np.float32),
        lon=lon.astype(np.float32), pop=pop,
    )

    print(f"total population in grid: {pop.sum():,.0f}")
    print(f"lat range: {lat.min():.2f} .. {lat.max():.2f}")
    print(f"lon range: {lon.min():.2f} .. {lon.max():.2f}")

    # Round-trip check: the projection origin must land on 52N 10E.
    olat, olon = laea_to_wgs84(np.array([X0]), np.array([Y0]))
    print(f"origin check: ({olat[0]:.6f}, {olon[0]:.6f}) expected (52.000000, 10.000000)")

    print("\nmost populated cells (sanity check on the projection):")
    for i in np.argsort(-pop)[:10]:
        print(f"  {pop[i]:9,.0f}  ({lat[i]:.4f}, {lon[i]:.4f})")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
