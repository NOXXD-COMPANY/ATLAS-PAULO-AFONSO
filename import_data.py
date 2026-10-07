#!/usr/bin/env python3
"""Importa edificações (Overture) e endereços (QG/CNEFE) para o MySQL:
uma linha por endereço, mais os prédios sem nenhum endereço."""

import json
import math
from collections import Counter

import pymysql

from shapely.geometry import Point, shape, mapping
from shapely.ops import transform
from shapely import strtree

DATA_DIR = "data/raw"
OVERTURE_FILES = [
    f"{DATA_DIR}/overture/overture-2026-08-19.0-building--38.236,-9.410,-38.212,-9.395.geojson",
    f"{DATA_DIR}/overture/overture-2026-08-19.0-building-municipio.geojson",
]
# 2ª fonte (API aberta Overpass/OSM, sem login): fallback onde o Overture
# não tem polígono. Ausência do arquivo só desliga o fallback.
OSM_BUILDINGS = f"{DATA_DIR}/osm/osm_buildings_paulo_afonso.geojson"
MUNICIPIO_BOUNDARY = f"{DATA_DIR}/municipio_boundary.geojson"
QG_ENDERECOS = f"{DATA_DIR}/qg/qg_810_endereco_Munic2924009.json"
MUNICIPIO = "2924009"  # Paulo Afonso/BA

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "atlas"
DB_PASSWORD = "atlas"
DB_NAME = "atlas_urbano"

# ~15 m de tolerância na borda (ex.: porta na fachada, erro de GPS).
POINT_TOLERANCE_DEG = 0.000135

# Raio do círculo usado para endereços sem prédio (~5 m).
POINT_BUFFER_DEG = 0.000045

SCHEMA = """
CREATE TABLE IF NOT EXISTS buildings (
    id                  VARCHAR(64)  NOT NULL PRIMARY KEY,
    geom                GEOMETRY     NOT NULL,
    area_m2             DOUBLE       NULL,
    tipo                VARCHAR(32)  NOT NULL DEFAULT 'desconhecido',
    endereco            VARCHAR(255) NULL,
    bairro              VARCHAR(128) NULL,
    estabelecimento     VARCHAR(255) NULL,
    num_pavimentos      INT          NULL,
    fonte               VARCHAR(128) NULL,
    SPATIAL INDEX idx_geom (geom)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# COD_ESPECIE do QG (CNEFE/IBGE) -> tipo de uso. Códigos oficiais:
# 1=domicílio particular, 2=domicílio coletivo, 3=agropecuário,
# 4=ensino, 5=saúde, 6=outras finalidades, 7=em construção,
# 8=religioso. Sem categoria para "em construção": desconhecido.
ESPECIE_TO_TIPO = {
    "1": "residencial",
    "2": "hospedagem",
    "3": "agropecuario",
    "4": "institucional",
    "5": "servico",
    "6": "comercial",
    "7": "desconhecido",
    "8": "religioso",
}

# Fallback para prédios sem ponto QG associado.
OVAERTURE_SUBTYPE_TO_TIPO = {
    "residential": "residencial",
    "commercial": "comercial",
    "religious": "religioso",
    "civic": "institucional",
    "medical": "servico",
    "education": "institucional",
    "transportation": "servico",
    "entertainment": "servico",
    "outbuilding": "desconhecido",
}
OVERTURE_CLASS_TO_TIPO = {
    "house": "residencial",
    "retail": "comercial",
    "church": "religioso",
    "school": "institucional",
    "library": "institucional",
    "post_office": "institucional",
    "hotel": "hospedagem",
    "roof": "desconhecido",
}


def connect_db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, charset="utf8mb4"
    )


def _area_m2(polygon) -> float:
    """Área aproximada em m², projetando localmente ao redor do próprio prédio."""
    cx, cy = polygon.centroid.x, polygon.centroid.y
    kx = 111320.0 * math.cos(math.radians(cy))
    ky = 110540.0

    def _to_meters(lon, lat):
        return (lon - cx) * kx, (lat - cy) * ky

    return transform(_to_meters, polygon).area


def load_buildings():
    """Junta os arquivos Overture (dedupe por id) e recorta no município."""
    merged = {}
    for path in OVERTURE_FILES:
        try:
            with open(path) as f:
                fc = json.load(f)
        except FileNotFoundError:
            print(f"  (aviso: {path} não encontrado, pulando)")
            continue
        for feat in fc["features"]:
            merged.setdefault(feat["id"], feat)
    features = list(merged.values())
    try:
        boundary = boundary_shape()
        from shapely.prepared import prep
        prepared = prep(boundary)
        before = len(features)
        features = [b for b in features
                    if prepared.intersects(shape(b["geometry"]))]
        print(f"  {before} prédios no bbox, {len(features)} dentro do município")
    except FileNotFoundError:
        print("  (aviso: contorno do município ausente, sem recorte)")
    return features


def boundary_shape():
    """Contorno do município (FeatureCollection ou Feature único)."""
    with open(MUNICIPIO_BOUNDARY) as f:
        doc = json.load(f)
    if doc.get("type") == "FeatureCollection":
        doc = doc["features"][0]
    return shape(doc["geometry"])


def load_osm_buildings():
    """2ª fonte: polígonos do OSM (fallback). [] se o arquivo não existir."""
    try:
        with open(OSM_BUILDINGS) as f:
            fc = json.load(f)
    except FileNotFoundError:
        return []
    features = fc["features"]
    try:
        boundary = boundary_shape()
        from shapely.prepared import prep
        prepared = prep(boundary)
        before = len(features)
        features = [b for b in features
                    if prepared.intersects(shape(b["geometry"]))]
        print(f"  OSM: {before} no bbox, {len(features)} dentro do município")
    except FileNotFoundError:
        pass
    return features


def load_qg_points():
    with open(QG_ENDERECOS) as f:
        fc = json.load(f)
    return fc["features"]


def best_type(qg_props, overture_props):
    especie = (qg_props or {}).get("COD_ESPECIE")
    if especie in ESPECIE_TO_TIPO:
        return ESPECIE_TO_TIPO[especie]
    subtype = (overture_props or {}).get("subtype")
    if subtype in OVAERTURE_SUBTYPE_TO_TIPO:
        return OVAERTURE_SUBTYPE_TO_TIPO[subtype]
    cls = (overture_props or {}).get("class")
    if cls in OVERTURE_CLASS_TO_TIPO:
        return OVERTURE_CLASS_TO_TIPO[cls]
    return "desconhecido"


def match_points(polys, points, q_indices=None):
    """Associa pontos a polígonos: contém → tolerância de ~15 m → mais próximo."""
    tree = strtree.STRtree(polys)
    if q_indices is None:
        q_indices = range(len(points))
    point_to_poly = {}
    for qi in q_indices:
        x, y = points[qi]["geometry"]["coordinates"]
        pt = Point(x, y)
        hits = tree.query(pt, predicate="contains")
        if len(hits) == 0:
            hits = tree.query(pt.buffer(POINT_TOLERANCE_DEG), predicate="intersects")
        if len(hits) == 0:
            continue
        cands = [int(i) for i in hits]
        best = min(cands, key=lambda bi: pt.distance(polys[bi]))
        point_to_poly[qi] = best
    return point_to_poly


def relate_points_to_buildings(buildings, points):
    polys = []
    for b in buildings:
        g = shape(b["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        polys.append(g)

    point_to_building = match_points(polys, points)
    building_to_points = {}
    for qi, bi in point_to_building.items():
        building_to_points.setdefault(bi, []).append(qi)
    return building_to_points, polys


def main():
    print("Lendo edificações do Overture...")
    building_features = load_buildings()
    print(f"  {len(building_features)} prédios")

    print("Lendo endereços do QG...")
    qg_features = load_qg_points()
    print(f"  {len(qg_features)} pontos de endereço")

    print("Relacionando endereços x prédios (espacialmente)...")
    building_to_points, polys = relate_points_to_buildings(building_features, qg_features)
    point_to_building = {
        qi: bi for bi, qis in building_to_points.items() for qi in qis
    }
    print(f"  {len(point_to_building)} endereços dentro de prédios")

    print("2ª fonte (OSM) para os endereços restantes...")
    osm_features = load_osm_buildings()
    osm_polys = []
    for b in osm_features:
        g = shape(b["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        osm_polys.append(g)
    unmatched = [qi for qi in range(len(qg_features))
                 if qi not in point_to_building]
    osm_match = (match_points(osm_polys, qg_features, unmatched)
                 if osm_polys else {})
    print(f"  OSM: {len(osm_features)} polígonos, "
          f"{len(osm_match)} endereços adotados")

    print("Gravando no MySQL...")
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS buildings")
            cur.execute(SCHEMA)

            codes = [str(q["properties"].get("COD_UNICO_ENDERECO")) for q in qg_features]
            dupes = {c for c, n in Counter(codes).items() if n > 1}
            seen = Counter()

            def row_id(code):
                if code not in dupes:
                    return code
                seen[code] += 1
                return f"{code}#{seen[code]}"

            def fonte_of(props):
                sources = props.get("sources") or []
                return "; ".join(dict(s).get("dataset", "?") for s in sources) or None

            batch = []
            for qi, qf in enumerate(qg_features):
                qp = qf["properties"]
                bi = point_to_building.get(qi)
                if bi is not None:
                    oprops = building_features[bi]["properties"]
                    geom = polys[bi]
                    num_pav = oprops.get("num_floors")
                    fonte = fonte_of(oprops)
                elif qi in osm_match:
                    oi = osm_match[qi]
                    otags = osm_features[oi]["properties"] or {}
                    oprops = {"class": otags.get("building")}
                    geom = osm_polys[oi]
                    num_pav = None
                    fonte = "OpenStreetMap"
                else:
                    oprops = {}
                    x, y = qf["geometry"]["coordinates"]
                    geom = Point(x, y).buffer(POINT_BUFFER_DEG)
                    num_pav = None
                    fonte = "QG/CNEFE"
                batch.append((
                    row_id(codes[qi]), json.dumps(mapping(geom)), _area_m2(geom),
                    best_type(qp, oprops),
                    qp.get("LOGRAD_NUM") or None, qp.get("DSC_LOCALIDADE") or None,
                    qp.get("DSC_ESTABELECIMENTO") or None, num_pav, fonte,
                ))

            for bi, b in enumerate(building_features):
                if bi in building_to_points:
                    continue
                props = b["properties"]
                geom = polys[bi]
                batch.append((
                    b["id"], json.dumps(mapping(geom)), _area_m2(geom),
                    best_type(None, props),
                    None, None, None, props.get("num_floors"), fonte_of(props),
                ))

            osm_to_points = {}
            for qi, oi in osm_match.items():
                osm_to_points.setdefault(oi, []).append(qi)
            for oi, o in enumerate(osm_features):
                if oi in osm_to_points:
                    continue
                otags = o["properties"] or {}
                oid = str(otags.get("osm_id", oi)).replace("/", "-")
                batch.append((
                    f"osm-{oid}", json.dumps(mapping(osm_polys[oi])),
                    _area_m2(osm_polys[oi]),
                    best_type(None, {"class": otags.get("building")}),
                    None, None, None, None, "OpenStreetMap",
                ))

            # SRID 0 em toda a tabela (tudo em lon/lat).
            sql = (
                "INSERT INTO buildings "
                "(id, geom, area_m2, tipo, endereco, bairro, estabelecimento, num_pavimentos, fonte) "
                "VALUES (%s, ST_GeomFromGeoJSON(%s), %s, %s, %s, %s, %s, %s, %s)"
            )
            CHUNK = 500
            for i in range(0, len(batch), CHUNK):
                cur.executemany(sql, batch[i:i + CHUNK])
            conn.commit()
            cur.execute("SELECT COUNT(*), SUM(tipo='desconhecido') FROM buildings")
            total, unknown = cur.fetchone()
            print(f"  Inseridos {total} prédios em `buildings` "
                  f"({unknown} sem tipo identificado = desconhecido)")
    finally:
        conn.close()
    print("Done.")


if __name__ == "__main__":
    main()