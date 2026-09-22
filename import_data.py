#!/usr/bin/env python3
"""Importa edificações (Overture) e endereços (QG/CNEFE) para o MySQL."""

import json
import math

import pymysql

from shapely.geometry import Point, shape, mapping
from shapely.ops import transform
from shapely import strtree

DATA_DIR = "data/raw"
OVERTURE_BUILDINGS = (
    f"{DATA_DIR}/overture/overture-2026-08-19.0-building--38.236,-9.410,-38.212,-9.395.geojson"
)
QG_ENDERECOS = f"{DATA_DIR}/qg/qg_810_endereco_Munic2924009.json"
MUNICIPIO = "2924009"  # Paulo Afonso/BA

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "atlas"
DB_PASSWORD = "atlas"
DB_NAME = "atlas_urbano"

# ~6 m de tolerância na borda (ex.: porta na fachada).
POINT_TOLERANCE_DEG = 0.00006

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

# COD_ESPECIE do QG (CNEFE/IBGE) -> tipo de uso.
ESPECIE_TO_TIPO = {
    "1": "residencial",
    "2": "hospedagem",
    "3": "agropecuario",
    "4": "institucional",
    "5": "servico",
    "6": "comercial",
    "7": "misto",
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
    with open(OVERTURE_BUILDINGS) as f:
        fc = json.load(f)
    return fc["features"]


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


def relate_points_to_buildings(buildings, points):
    polys = []
    for b in buildings:
        g = shape(b["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        polys.append(g)

    tree = strtree.STRtree(polys)

    point_to_building = {}
    for qi, feat in enumerate(points):
        x, y = feat["geometry"]["coordinates"]
        pt = Point(x, y)
        hits = tree.query(pt, predicate="contains")
        if len(hits) == 0:
            hits = tree.query(pt.buffer(POINT_TOLERANCE_DEG), predicate="intersects")
        if len(hits) == 0:
            continue
        cands = [int(i) for i in hits]
        best = min(cands, key=lambda bi: pt.distance(polys[bi]))
        point_to_building[qi] = best

    building_to_points = {}
    for qi, bi in point_to_building.items():
        building_to_points.setdefault(bi, []).append(qi)
    return building_to_points, polys


def pick_preferred_point(qg_indices, points):
    def score(qi):
        p = points[qi]["properties"]
        has_estab = bool(p.get("DSC_ESTABELECIMENTO"))
        has_addr = bool(p.get("LOGRAD_NUM"))
        especie = p.get("COD_ESPECIE")
        is_home = especie == "1"
        if has_estab and not is_home:
            return 3
        if has_estab:
            return 2
        if has_addr:
            return 1
        return 0

    return max(qg_indices, key=score)


def main():
    print("Lendo edificações do Overture...")
    building_features = load_buildings()
    print(f"  {len(building_features)} prédios")

    print("Lendo endereços do QG...")
    qg_features = load_qg_points()
    print(f"  {len(qg_features)} pontos de endereço")

    print("Relacionando endereços x prédios (espacialmente)...")
    building_to_points, polys = relate_points_to_buildings(building_features, qg_features)
    matched_buildings = len(building_to_points)
    print(f"  {matched_buildings} prédios receberam endereço "
          f"({100 * matched_buildings / max(len(building_features), 1):.1f}%)")

    print("Gravando no MySQL...")
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS buildings")
            cur.execute(SCHEMA)

            batch = []
            for bi, b in enumerate(building_features):
                props = b["properties"]
                geom = polys[bi]

                qg_props = None
                if bi in building_to_points:
                    preferred = pick_preferred_point(building_to_points[bi], qg_features)
                    qg_props = qg_features[preferred]["properties"]

                endereco = (qg_props or {}).get("LOGRAD_NUM") or None
                bairro = (qg_props or {}).get("DSC_LOCALIDADE") or None
                estabelecimento = (qg_props or {}).get("DSC_ESTABELECIMENTO") or None
                num_pav = props.get("num_floors")
                tipo = best_type(qg_props, props)

                sources = props.get("sources") or []
                fonte = "; ".join(dict(s).get("dataset", "?") for s in sources) or None

                batch.append((
                    b["id"], json.dumps(mapping(geom)), _area_m2(geom),
                    tipo, endereco, bairro, estabelecimento, num_pav, fonte,
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