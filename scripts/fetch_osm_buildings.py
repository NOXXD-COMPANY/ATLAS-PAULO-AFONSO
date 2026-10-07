#!/usr/bin/env python3
"""Baixa polígonos de edificações do OpenStreetMap via API Overpass.

API aberta, sem login e sem custo (licença ODbL, compatível com o projeto).
Uso moderado: 1 consulta de contorno + N consultas por célula da grade.

Saída: data/raw/osm/osm_buildings_paulo_afonso.geojson
       (Polygon/MultiPolygon, properties.osm_id + tags building/*)

Uso: ./.venv/bin/python scripts/fetch_osm_buildings.py
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from shapely.geometry import mapping, Polygon

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
MUNICIPIO = "Paulo Afonso"
ADMIN_LEVEL = "8"
OUT_DIR = Path("data/raw/osm")
OUT_FILE = OUT_DIR / "osm_buildings_paulo_afonso.geojson"
BBOX_FILE = OUT_DIR / "municipio_bbox.json"  # cache (via Nominatim, 1 request)
GRID = 6  # 6x6 células: consultas menores evitam o timeout do servidor
TIMEOUT_S = 120
PAUSA_S = 8


def overpass(query: str, timeout: int = 180):
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=data, method="POST", headers={
        "User-Agent": "atlas-urbano/0.1 (projeto universitário; contato via repo)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout + 30) as res:
        return json.load(res)


def fetch_boundary():
    print("Buscando contorno do município...")
    q = f"""[out:json][timeout:{TIMEOUT_S}];
relation["boundary"="administrative"]["admin_level"="{ADMIN_LEVEL}"]["name"="{MUNICIPIO}"];
out geom;"""
    payload = overpass(q, TIMEOUT_S)
    coords = []
    for el in payload.get("elements", []):
        for m in el.get("members", []):
            g = m.get("geometry")
            if g:
                coords.extend([(p["lon"], p["lat"]) for p in g])
    if not coords:
        sys.exit("ERRO: contorno do município não encontrado no OSM.")
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    print(f"  bbox do município: {bbox}")
    return bbox


def fetch_cell(s, w, n, e):
    # Só ways: relations com tag building são raríssimas e o `out geom`
    # delas é o que estoura o timeout do servidor público.
    q = f"""[out:json][timeout:{TIMEOUT_S}];
way["building"]({s},{w},{n},{e});
out geom;"""
    return overpass(q, TIMEOUT_S).get("elements", [])


def assemble(elements):
    """OSM JSON -> lista de (osm_id, shapely geom, tags)."""
    nodes = {}
    ways = {}
    for el in elements:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
        elif el["type"] == "way":
            g = el.get("geometry")
            if g:
                ways[el["id"]] = ([(p["lon"], p["lat"]) for p in g],
                                  el.get("tags", {}))
    geoms = []

    def ring_of(pts):
        if len(pts) >= 3 and pts[0] != pts[-1]:
            pts = pts + [pts[0]]
        if len(pts) < 4:
            return None
        try:
            p = Polygon(pts)
            return p if not p.is_empty else None
        except Exception:
            return None

    for wid, (pts, tags) in ways.items():
        r = ring_of(pts)
        if r is not None:
            geoms.append((f"way/{wid}", r, tags))
    for el in elements:
        if el["type"] != "relation":
            continue
        outers, inners = [], []
        for m in el.get("members", []):
            if m["type"] != "way" or not m.get("geometry"):
                continue
            r = ring_of([(p["lon"], p["lat"]) for p in m["geometry"]])
            if r is None:
                continue
            (inners if m.get("role") == "inner" else outers).append(r)
        for o in outers:
            holes = [i.exterior.coords[:] for i in inners
                     if o.contains(i) or o.intersects(i)]
            try:
                geoms.append((f"relation/{el['id']}",
                              Polygon(o.exterior.coords[:], holes),
                              el.get("tags", {})))
            except Exception:
                geoms.append((f"relation/{el['id']}", o, el.get("tags", {})))
    return geoms


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if BBOX_FILE.exists():
        minx, miny, maxx, maxy = json.loads(BBOX_FILE.read_text())["bbox"]
        print(f"bbox do município (cache): {(minx, miny, maxx, maxy)}")
    else:
        minx, miny, maxx, maxy = fetch_boundary()
    dx, dy = (maxx - minx) / GRID, (maxy - miny) / GRID
    cells = []
    for i in range(GRID):
        for j in range(GRID):
            cells.append((miny + i * dy, minx + j * dx,
                          miny + (i + 1) * dy, minx + (j + 1) * dx))
    seen, features = set(), []

    def colher(s, w, n, e, rotulo):
        print(f"{rotulo} ...", flush=True)
        elements = fetch_cell(s, w, n, e)
        n0 = len(features)
        for oid, geom, tags in assemble(elements):
            if oid in seen:
                continue
            seen.add(oid)
            if not geom.is_valid:
                geom = geom.buffer(0)
            if geom.is_empty:
                continue
            features.append({
                "type": "Feature",
                "id": oid,
                "geometry": mapping(geom),
                "properties": {
                    "osm_id": oid,
                    "building": (tags or {}).get("building"),
                },
            })
        print(f"  +{len(features) - n0} polígonos")
        time.sleep(PAUSA_S)  # gentileza com o servidor público

    # Passada 1: grade cheia.
    falharam = []
    for k, (s, w, n, e) in enumerate(cells):
        try:
            colher(s, w, n, e, f"Célula {k + 1}/{len(cells)}")
        except Exception as exc:
            print(f"  falhou ({exc}), vai para a repescagem")
            falharam.append((s, w, n, e))
    # Passada 2: repescagem subdividida (consultas menores).
    for k, (s, w, n, e) in enumerate(falharam):
        mx, my = (w + e) / 2, (s + n) / 2
        for q, (s2, w2, n2, e2) in enumerate(
                [(s, w, my, mx), (s, mx, my, e),
                 (my, w, n, mx), (my, mx, n, e)]):
            try:
                colher(s2, w2, n2, e2, f"Repescagem {k + 1}.{q + 1}")
            except Exception as exc:
                print(f"  falhou de novo ({exc}), desistindo do quadrante")
    fc = {"type": "FeatureCollection", "features": features}
    OUT_FILE.write_text(json.dumps(fc))
    print(f"Salvos {len(features)} polígonos em {OUT_FILE}")


if __name__ == "__main__":
    main()
