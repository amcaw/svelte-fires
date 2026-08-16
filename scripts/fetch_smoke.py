#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import cdsapi
import netCDF4
import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "static" / "data"
GRIDS = DATA / "smoke"

ADS = "https://ads.atmosphere.copernicus.eu/api"
DATASET = "cams-europe-air-quality-forecasts"
VARIABLE = "pm10_wildfires"
CAMS_RETREAT = 2
UNIT = "µg/m³"

WEST, SOUTH, EAST, NORTH = -12.0, 34.0, 34.0, 62.0
COORDS = ("longitude", "latitude", "level", "time", "valid_time", "forecast_period", "forecast_reference_time")


def parse_args():
    p = argparse.ArgumentParser(description="Fetch CAMS Europe wildfire PM10 over Europe, one grid per day.")
    p.add_argument("--since", default="", help="First day (default: meta.json since).")
    p.add_argument("--until", default="", help="Last day (default: meta.json until).")
    p.add_argument("--hours", default="0,4,8,12,16,20", help="Hours of day to fetch, UTC.")
    p.add_argument("--floor", type=float, default=0.1, help="Values below this are written as 0.")
    p.add_argument("--from-file", default="", help="Rebuild from an existing NetCDF, no download.")
    p.add_argument("--keep", default="", help="Keep the downloaded NetCDF at this path.")
    return p.parse_args()


def window(args) -> tuple[dt.date, dt.date]:
    meta = json.loads((DATA / "meta.json").read_text())
    since = dt.date.fromisoformat(args.since or meta["since"])
    steps = meta.get("activeDates") or []
    until = dt.date.fromisoformat(args.until or (steps[-1][:10] if steps else meta["until"]))
    if until < since:
        sys.exit(f"until ({until}) is before since ({since})")
    return since, until


def api_key() -> str:
    key = os.environ.get("ADS_API_KEY", "")
    if key:
        return key
    rc = Path.home() / ".cdsapirc"
    if rc.exists():
        for line in rc.read_text().splitlines():
            if line.split(":", 1)[0].strip() == "key":
                return line.split(":", 1)[1].strip()
    sys.exit("no ADS key — set ADS_API_KEY or put one in ~/.cdsapirc")


def download(since: dt.date, until: dt.date, hours: list[int], target: Path) -> None:
    client = cdsapi.Client(url=ADS, key=api_key())
    request = {
        "variable": [VARIABLE],
        "model": ["ensemble"],
        "level": ["0"],
        "date": [f"{since.isoformat()}/{until.isoformat()}"],
        "type": ["forecast"],
        "time": ["00:00"],
        "leadtime_hour": [str(h) for h in hours],
        "data_format": "netcdf",
        "area": [NORTH, WEST, SOUTH, EAST],
    }
    print(f"[cams] {DATASET} {VARIABLE} {since} → {until}, {len(hours)} pas/jour", flush=True)
    client.retrieve(DATASET, request, str(target))


def read_grid(path: Path):
    with netCDF4.Dataset(path) as ds:
        name = next(v for v in ds.variables if v not in COORDS)
        raw = ds.variables[name][:]
        lon = np.asarray(ds.variables["longitude"][:], dtype=float)
        lat = np.asarray(ds.variables["latitude"][:], dtype=float)
        stamp = ds.variables["valid_time" if "valid_time" in ds.variables else "time"]
        hours = np.atleast_1d(np.asarray(stamp[:], dtype=float)).ravel()
        origin = re.search(r"(\d{8})", getattr(stamp, "long_name", ""))
        if origin:
            start = dt.datetime.strptime(origin.group(1), "%Y%m%d")
            moments = [start + dt.timedelta(hours=float(h)) for h in hours]
        else:
            moments = list(
                np.atleast_1d(netCDF4.num2date(stamp[:], stamp.units, only_use_cftime_datetimes=False)).ravel()
            )

    values = np.asarray(np.ma.filled(raw, np.nan), dtype=float)
    while values.ndim > 3:
        values = values[:, 0]
    if values.ndim == 2:
        values = values[None, :, :]
    lon = np.where(lon > 180.0, lon - 360.0, lon)
    return values, lon, lat, [f"{m:%Y-%m-%d_%H}" for m in moments]


def write_day(values: np.ndarray, lon: np.ndarray, lat: np.ndarray, floor: float, path: Path) -> float:
    order_lon = np.argsort(lon)
    order_lat = np.argsort(lat)[::-1]
    field = values[:, order_lon][order_lat, :]

    step_lon = float(np.median(np.diff(np.sort(lon)))) if lon.size > 1 else 0.1
    step_lat = float(np.median(np.abs(np.diff(lat)))) if lat.size > 1 else 0.1
    west, east = float(lon.min()) - step_lon / 2, float(lon.max()) + step_lon / 2
    south, north = float(lat.min()) - step_lat / 2, float(lat.max()) + step_lat / 2

    clean = np.where(np.isfinite(field), field, 0.0)
    clean = np.where(clean < floor, 0.0, clean)
    tenths = np.rint(clean * 10.0).astype(int)

    runs: list[int] = []
    for value in tenths.ravel():
        value = int(value)
        if runs and runs[-2] == value:
            runs[-1] += 1
        else:
            runs.extend((value, 1))

    path.write_text(
        json.dumps(
            {
                "nx": int(clean.shape[1]),
                "ny": int(clean.shape[0]),
                "scale": 10,
                "bounds": [round(west, 4), round(south, 4), round(east, 4), round(north, 4)],
                "rle": runs,
            },
            separators=(",", ":"),
        )
    )
    return float(tenths.max()) / 10.0


def main() -> None:
    args = parse_args()
    since, until = window(args)

    hours = [int(h) for h in args.hours.split(",") if h.strip()]

    with tempfile.TemporaryDirectory() as tmp:
        if args.from_file:
            raw = Path(args.from_file)
        else:
            raw = Path(args.keep) if args.keep else Path(tmp) / "cams.nc"
            for retreat in range(CAMS_RETREAT + 1):
                try:
                    download(since, until, hours, raw)
                    break
                except Exception as e:
                    if retreat == CAMS_RETREAT or until <= since:
                        raise
                    print(f"[cams] {until} indisponible ({e}) — on recule d'un jour", flush=True)
                    until -= dt.timedelta(days=1)
        values, lon, lat, moments = read_grid(raw)

    if GRIDS.exists():
        shutil.rmtree(GRIDS)
    GRIDS.mkdir(parents=True)

    # on s'aligne sur les pas des feux actifs : eux seuls savent jusqu'où la
    # donnée observée va. Sinon on publierait des prévisions CAMS pour des heures
    # à venir, au-dessus d'une carte de foyers vide.
    allowed = set(json.loads((DATA / "meta.json").read_text()).get("activeDates") or [])
    if not allowed:
        cutoff = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        allowed = {s for s in moments if dt.datetime.strptime(s, "%Y-%m-%d_%H") <= cutoff}

    peak = 0.0
    stamps: list[str] = []
    for i, stamp in enumerate(moments):
        if stamp not in allowed:
            continue
        peak = max(peak, write_day(values[i], lon, lat, args.floor, GRIDS / f"{stamp}.json"))
        stamps.append(stamp)
    stamps.sort()
    dropped = len(moments) - len(stamps)
    if dropped:
        print(f"[cams] {dropped} pas écartés, hors de la fenêtre observée")

    meta_path = DATA / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta["smoke"] = {
        "variable": VARIABLE,
        "unit": UNIT,
        "hours": hours,
        "dates": stamps,
        "peak": round(peak, 1),
        "source": "CAMS European air quality forecasts (Copernicus / ECMWF)",
    }
    meta_path.write_text(json.dumps(meta, separators=(",", ":")))

    total = sum(f.stat().st_size for f in GRIDS.glob("*.json"))
    print(f"[cams] {len(stamps)} grilles {values.shape[2]}×{values.shape[1]}, pic {peak:.1f} {UNIT}")
    print(f"[cams] {total / 1e6:.1f} MB au total, {total / max(len(stamps), 1) / 1e3:.0f} kB par pas")


if __name__ == "__main__":
    main()
