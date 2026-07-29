#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import os
import shutil
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = HERE / ".env"
DATA = HERE.parent / "static" / "data"

EFFIS = "https://maps.effis.emergency.copernicus.eu/effis"
EFFIS_LAYER = "ms:modis.ba.poly"
FIRMS = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
FIRMS_CHUNK = 5
FIRMS_HISTORY_CHUNK = 5
ACTIVE_DIR = DATA / "active"

BBOX = (-12.0, 34.0, 34.0, 62.0)
NON_EUROPE = {"DZ", "TN", "MA", "LY", "EG", "LB", "SY", "IL", "PS", "JO", "IQ", "IR", "SA", "KW", "YE"}


def parse_args():
    p = argparse.ArgumentParser(description="Fetch EFFIS burnt areas and FIRMS active fires for Europe.")
    p.add_argument("--since", default="2026-07-01", help="First fire date kept (YYYY-MM-DD).")
    p.add_argument("--until", default="", help="Last fire date kept (default: latest available).")
    p.add_argument("--hours", type=int, default=48, help="Active-fire window, hours back from now.")
    p.add_argument("--min-ha", type=float, default=1.0, help="Drop burnt areas smaller than this.")
    p.add_argument("--tolerance", type=float, default=0.0012, help="Polygon simplification, degrees.")
    p.add_argument("--sources", default="VIIRS_NOAA20_NRT,VIIRS_SNPP_NRT,MODIS_NRT")
    p.add_argument("--skip-effis", action="store_true")
    p.add_argument("--skip-firms", action="store_true")
    p.add_argument("--history", action="store_true", help="Also fetch FIRMS day by day over the whole window.")
    return p.parse_args()


def get_json(url: str, timeout: int = 300, tries: int = 3):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == tries - 1:
                sys.exit(f"request failed: {e}\n  {url[:160]}")
    return {}


def round_coords(node, precision: int):
    if isinstance(node, list):
        if node and isinstance(node[0], (int, float)):
            return [round(float(v), precision) for v in node]
        return [round_coords(v, precision) for v in node]
    return node


ARTICLES = {"le", "la", "les", "l'", "el", "els", "lo", "los", "las", "il", "i", "a", "o", "as", "os"}


def tidy(name: str) -> str:
    name = (name or "").strip()
    if "," not in name:
        return name
    head, tail = name.rsplit(",", 1)
    if tail.strip().lower() in ARTICLES:
        return f"{tail.strip()} {head.strip()}"
    return name


def largest_ring_centroid(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    best, best_span = None, -1.0
    for poly in polys:
        ring = poly[0]
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        span = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if span > best_span:
            best_span, best = span, ring
    if not best:
        return None
    return [round(sum(p[0] for p in best) / len(best), 4),
            round(sum(p[1] for p in best) / len(best), 4)]


def fetch_effis(args):
    flt = ("<Filter><PropertyIsGreaterThanOrEqualTo><PropertyName>FIREDATE</PropertyName>"
           f"<Literal>{args.since}</Literal></PropertyIsGreaterThanOrEqualTo></Filter>")
    q = urllib.parse.urlencode({
        "service": "WFS", "version": "1.1.0", "request": "GetFeature",
        "typename": EFFIS_LAYER, "outputformat": "geojson", "srsname": "EPSG:4326", "filter": flt,
    })
    print(f"[effis] {EFFIS_LAYER} since {args.since}", flush=True)
    raw = get_json(f"{EFFIS}?{q}").get("features", [])
    print(f"  {len(raw)} features returned")

    from shapely.geometry import shape, mapping

    since = dt.date.fromisoformat(args.since)
    until = dt.date.fromisoformat(args.until) if args.until else None

    kept, per_country, latest = [], defaultdict(lambda: [0.0, 0]), since
    for f in raw:
        p = f["properties"]
        country = (p.get("COUNTRY") or "??").strip()
        if country in NON_EUROPE:
            continue
        try:
            date = dt.date.fromisoformat(str(p["FIREDATE"])[:10])
        except Exception:
            continue
        if date < since or (until and date > until):
            continue
        ha = float(p.get("AREA_HA") or 0)
        if ha < args.min_ha:
            continue
        g = shape(f["geometry"]).buffer(0)
        if g.is_empty:
            continue
        g = g.simplify(args.tolerance, preserve_topology=True)
        if g.is_empty:
            continue
        geom = round_coords(json.loads(json.dumps(mapping(g))), 4)
        place = ", ".join(x for x in [tidy(p.get("COMMUNE")), tidy(p.get("PROVINCE"))] if x)
        kept.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "ha": round(ha, 1),
                "date": date.isoformat(),
                "day": (date - since).days,
                "country": country,
                "place": (place or country)[:60],
            },
        })
        per_country[country][0] += ha
        per_country[country][1] += 1
        latest = max(latest, date)

    if not kept:
        sys.exit("no burnt areas kept — check --since / --until")

    kept.sort(key=lambda f: -f["properties"]["ha"])
    for rank, f in enumerate(kept, 1):
        f["properties"]["rank"] = rank

    top = [{
        "rank": f["properties"]["rank"],
        "ha": f["properties"]["ha"],
        "place": f["properties"]["place"],
        "country": f["properties"]["country"],
        "date": f["properties"]["date"],
        "at": largest_ring_centroid(f["geometry"]),
    } for f in kept[:12]]

    ranking = sorted(({"code": k, "ha": round(v[0]), "fires": v[1]} for k, v in per_country.items()),
                     key=lambda r: -r["ha"])

    write("burned.geojson", {"type": "FeatureCollection", "features": kept})
    return {
        "since": since.isoformat(),
        "until": latest.isoformat(),
        "days": (latest - since).days + 1,
        "fires": len(kept),
        "totalHa": round(sum(v[0] for v in per_country.values())),
        "ranking": ranking,
        "top": top,
    }


def firms_key() -> str:
    key = os.environ.get("FIRMS_MAP_KEY", "")
    if not key and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith("FIRMS_MAP_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit(f"no FIRMS_MAP_KEY — put it in {ENV} or the environment")
    return key


def fetch_firms(args):
    key = firms_key()
    bbox = ",".join(str(v) for v in BBOX)
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(hours=args.hours)
    start = cutoff.date()
    days = min(FIRMS_CHUNK, (now.date() - start).days + 1)

    print(f"[firms] {args.sources} · last {args.hours} h (from {cutoff:%Y-%m-%d %H:%M} UTC)", flush=True)

    points, seen = [], set()
    for source in [s.strip() for s in args.sources.split(",") if s.strip()]:
        url = f"{FIRMS}/{key}/{source}/{bbox}/{days}/{start.isoformat()}"
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                text = r.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  {source}: failed ({e})")
            continue
        if text.lstrip().startswith("<") or "Invalid" in text[:200]:
            print(f"  {source}: rejected — {text[:140]}")
            continue
        rows = list(csv.DictReader(io.StringIO(text)))
        got = 0
        for row in rows:
            try:
                clock = str(row["acq_time"]).zfill(4)
                stamp = dt.datetime.strptime(f"{row['acq_date']} {clock}", "%Y-%m-%d %H%M").replace(
                    tzinfo=dt.timezone.utc)
            except Exception:
                continue
            if stamp < cutoff:
                continue
            if str(row.get("confidence", "")).lower() in ("l", "low"):
                continue
            lon = round(float(row["longitude"]), 3)
            lat = round(float(row["latitude"]), 3)
            fingerprint = (lon, lat, stamp.hour, stamp.day)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            try:
                frp = round(float(row.get("frp") or 0), 1)
            except Exception:
                frp = 0.0
            points.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "frp": frp,
                    "hours": round((now - stamp).total_seconds() / 3600, 1),
                    "at": stamp.strftime("%Y-%m-%dT%H:%MZ"),
                },
            })
            got += 1
        print(f"  {source}: {len(rows)} rows → {got} kept")

    write("active.geojson", {"type": "FeatureCollection", "features": points})
    return {
        "activeHours": args.hours,
        "active": len(points),
        "activeUntil": now.strftime("%Y-%m-%dT%H:%MZ"),
        "activeFrpMax": max((p["properties"]["frp"] for p in points), default=0),
    }


def fetch_firms_history(args, since: dt.date, until: dt.date):
    key = firms_key()
    bbox = ",".join(str(v) for v in BBOX)
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    span = (until - since).days + 1

    print(f"[firms] historique {since} → {until} ({span} jours)", flush=True)

    per_day: dict[str, list[list[float]]] = defaultdict(list)
    seen = set()

    for source in sources:
        kept = 0
        cursor = since
        while cursor <= until:
            days = min(FIRMS_HISTORY_CHUNK, (until - cursor).days + 1)
            url = f"{FIRMS}/{key}/{source}/{bbox}/{days}/{cursor.isoformat()}"
            try:
                with urllib.request.urlopen(url, timeout=300) as r:
                    text = r.read().decode("utf-8", "replace")
            except Exception as e:
                print(f"  {source} {cursor}: failed ({e})")
                cursor += dt.timedelta(days=days)
                continue
            if text.lstrip().startswith("<") or "Invalid" in text[:200]:
                print(f"  {source} {cursor}: rejected — {text[:120]}")
                cursor += dt.timedelta(days=days)
                continue
            for row in csv.DictReader(io.StringIO(text)):
                try:
                    date = dt.date.fromisoformat(str(row["acq_date"])[:10])
                except Exception:
                    continue
                if date < since or date > until:
                    continue
                if str(row.get("confidence", "")).lower() in ("l", "low"):
                    continue
                lon = round(float(row["longitude"]), 3)
                lat = round(float(row["latitude"]), 3)
                fingerprint = (lon, lat, date)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                try:
                    frp = round(float(row.get("frp") or 0), 1)
                except Exception:
                    frp = 0.0
                per_day[date.isoformat()].append([lon, lat, frp])
                kept += 1
            cursor += dt.timedelta(days=days)
        print(f"  {source}: {kept} détections retenues")

    if ACTIVE_DIR.exists():
        shutil.rmtree(ACTIVE_DIR)
    ACTIVE_DIR.mkdir(parents=True)

    stamps = []
    for i in range(span):
        stamp = (since + dt.timedelta(days=i)).isoformat()
        (ACTIVE_DIR / f"{stamp}.json").write_text(
            json.dumps({"points": per_day.get(stamp, [])}, separators=(",", ":"))
        )
        stamps.append(stamp)

    total = sum(len(v) for v in per_day.values())
    weight = sum(f.stat().st_size for f in ACTIVE_DIR.glob("*.json"))
    print(f"  {total:,} détections sur {span} jours, {weight / 1e6:.1f} MB "
          f"({weight / max(span, 1) / 1e3:.0f} kB par jour)")

    return {"activeDates": stamps, "activeTotal": total}


def write(name: str, payload) -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / name
    path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    print(f"  wrote {path.relative_to(HERE.parent)} ({path.stat().st_size // 1024} KB)")
    return path


def main():
    args = parse_args()
    meta_path = DATA / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    if not args.skip_effis:
        meta.update(fetch_effis(args))
    if not args.skip_firms:
        meta.update(fetch_firms(args))
    if args.history:
        since = dt.date.fromisoformat(args.since)
        until = dt.date.fromisoformat(meta.get("until") or args.since)
        meta.update(fetch_firms_history(args, since, until))

    meta["bounds"] = [[BBOX[0], BBOX[1]], [BBOX[2], BBOX[3]]]
    meta["sources"] = {
        "burned": "Copernicus EMS / EFFIS — MODIS 250 m and Sentinel-2 20 m rapid damage assessment",
        "active": "NASA FIRMS — VIIRS (375 m) and MODIS (1 km) active fire detections",
        "basemap": "CARTO Positron / OpenStreetMap contributors",
    }
    meta["built"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    write("meta.json", meta)

    print(f"\n  {meta.get('fires', 0)} fires · {meta.get('totalHa', 0):,} ha "
          f"({meta.get('since')} → {meta.get('until')})")
    print(f"  {meta.get('active', 0):,} active detections in the last {meta.get('activeHours', 0)} h")
    for r in meta.get("ranking", [])[:8]:
        print(f"    {r['code']:4s} {r['ha']:9,d} ha  ({r['fires']} fires)")


if __name__ == "__main__":
    main()
