#!/usr/bin/env python3
"""Importa edificações (Overture) e endereços (QG/CNEFE) para o MySQL:
`buildings` tem uma linha por endereço, mais os prédios sem nenhum endereço;
`predios` tem um polígono por prédio, com o ponto no centro dele."""

import json
import math
from collections import Counter

import pymysql

from shapely.geometry import Point, shape
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

# ~30 m: endereço que sobrou adota o prédio sem endereço mais próximo.
ATTACH_TOLERANCE_DEG = 0.00027

# Raio do círculo usado para endereços sem prédio (~5 m).
POINT_BUFFER_DEG = 0.000045

# Carga em tabelas `*_new` e troca no fim: a API nunca vê tabela pela metade.
TABELAS = ("buildings", "predios")

SCHEMA_BUILDINGS = """
CREATE TABLE buildings_new (
    id                  VARCHAR(64)  NOT NULL PRIMARY KEY,
    geom                GEOMETRY     NOT NULL,
    area_m2             DOUBLE       NULL,
    tipo                VARCHAR(32)  NOT NULL DEFAULT 'desconhecido',
    endereco            VARCHAR(255) NULL,
    bairro              VARCHAR(128) NULL,
    estabelecimento     VARCHAR(255) NULL,
    num_pavimentos      INT          NULL,
    fonte               VARCHAR(128) NULL,
    predio_id           VARCHAR(64)  NOT NULL,
    SPATIAL INDEX idx_geom (geom),
    INDEX idx_predio (predio_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

SCHEMA_PREDIOS = """
CREATE TABLE predios_new (
    predio_id           VARCHAR(64)  NOT NULL PRIMARY KEY,
    geom                GEOMETRY     NOT NULL,
    ponto               POINT        NOT NULL,
    area_m2             DOUBLE       NULL,
    tipo                VARCHAR(32)  NOT NULL DEFAULT 'desconhecido',
    num_pavimentos      INT          NULL,
    fonte               VARCHAR(128) NULL,
    n_enderecos         INT          NOT NULL DEFAULT 0,
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


def match_points(polys, points, q_indices=None, tolerance=POINT_TOLERANCE_DEG):
    """Associa pontos a polígonos: contém → tolerância (padrão ~15 m) → mais próximo."""
    tree = strtree.STRtree(polys)
    if q_indices is None:
        q_indices = range(len(points))
    point_to_poly = {}
    for qi in q_indices:
        x, y = points[qi]["geometry"]["coordinates"]
        pt = Point(x, y)
        hits = tree.query(pt, predicate="contains")
        if len(hits) == 0:
            hits = tree.query(pt.buffer(tolerance), predicate="intersects")
        if len(hits) == 0:
            continue
        cands = [int(i) for i in hits]
        best = min(cands, key=lambda bi: pt.distance(polys[bi]))
        point_to_poly[qi] = best
    return point_to_poly


def valid_polys(features):
    polys = []
    for b in features:
        g = shape(b["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        polys.append(g)
    return polys


def associar(polys, osm_polys, points):
    """Endereço → prédio, em três passos:
    1. Overture (dentro ou a ~15 m);
    2. OSM, para os que sobraram (dentro ou a ~15 m);
    3. o prédio Overture ainda sem endereço mais próximo (até ~30 m).
    Retorna ({qi: índice Overture}, {qi: índice OSM})."""
    to_bldg = match_points(polys, points) if polys else {}
    resto = [qi for qi in range(len(points)) if qi not in to_bldg]
    to_osm = match_points(osm_polys, points, resto) if osm_polys and resto else {}
    resto = [qi for qi in resto if qi not in to_osm]
    livres = sorted(set(range(len(polys))) - set(to_bldg.values()))
    if livres and resto:
        sub = match_points([polys[i] for i in livres], points, resto,
                           ATTACH_TOLERANCE_DEG)
        to_bldg.update({qi: livres[j] for qi, j in sub.items()})
    return to_bldg, to_osm


def centro(geom):
    """Centro do prédio; se cair fora (prédio em L/U), um ponto garantido dentro."""
    c = geom.centroid
    return c if geom.contains(c) else geom.representative_point()


def tipo_dominante(tipos):
    """Tipo mais frequente entre os endereços; `desconhecido` só se não houver outro."""
    conhecidos = Counter(t for t in tipos if t != "desconhecido")
    return conhecidos.most_common(1)[0][0] if conhecidos else "desconhecido"


def fonte_of(props):
    sources = props.get("sources") or []
    return "; ".join(dict(s).get("dataset", "?") for s in sources) or None


def montar(building_features, qg_features, osm_features):
    """Monta as linhas de `buildings` (uma por endereço + prédios sem endereço)
    e de `predios` (um por polígono, com o ponto no centro). Não toca o banco."""
    polys = valid_polys(building_features)
    osm_polys = valid_polys(osm_features)
    to_bldg, to_osm = associar(polys, osm_polys, qg_features)

    codes = [str(q["properties"].get("COD_UNICO_ENDERECO")) for q in qg_features]
    dupes = {c for c, n in Counter(codes).items() if n > 1}
    seen = Counter()

    def row_id(code):
        if code not in dupes:
            return code
        seen[code] += 1
        return f"{code}#{seen[code]}"

    def osm_id(oi):
        otags = osm_features[oi]["properties"] or {}
        return "osm-" + str(otags.get("osm_id", oi)).replace("/", "-")

    predios = {}

    def add_predio(pid, geom, ponto, num_pav, fonte, tipo, endereco):
        p = predios.setdefault(pid, {"geom": geom, "ponto": ponto, "num_pav": num_pav,
                                     "fonte": fonte, "tipos": [], "n": 0})
        p["tipos"].append(tipo)
        p["n"] += endereco

    rows = []
    for qi, qf in enumerate(qg_features):
        qp = qf["properties"]
        rid = row_id(codes[qi])
        if qi in to_bldg:
            bi = to_bldg[qi]
            oprops = building_features[bi]["properties"]
            geom, pid = polys[bi], building_features[bi]["id"]
            num_pav, fonte = oprops.get("num_floors"), fonte_of(oprops)
            ponto = centro(geom)
        elif qi in to_osm:
            oi = to_osm[qi]
            otags = osm_features[oi]["properties"] or {}
            oprops = {"class": otags.get("building")}
            geom, pid = osm_polys[oi], osm_id(oi)
            num_pav, fonte = None, "OpenStreetMap"
            ponto = centro(geom)
        else:
            oprops = {}
            x, y = qf["geometry"]["coordinates"]
            ponto = Point(x, y)
            geom, pid = ponto.buffer(POINT_BUFFER_DEG), rid
            num_pav, fonte = None, "QG/CNEFE"
        tipo = best_type(qp, oprops)
        rows.append((
            rid, geom.wkt, _area_m2(geom), tipo,
            qp.get("LOGRAD_NUM") or None, qp.get("DSC_LOCALIDADE") or None,
            qp.get("DSC_ESTABELECIMENTO") or None, num_pav, fonte, pid,
        ))
        add_predio(pid, geom, ponto, num_pav, fonte, tipo, 1)

    com_endereco = set(to_bldg.values())
    for bi, b in enumerate(building_features):
        geom = polys[bi]
        if bi in com_endereco or geom.is_empty:
            continue
        props = b["properties"]
        tipo, fonte = best_type(None, props), fonte_of(props)
        rows.append((
            b["id"], geom.wkt, _area_m2(geom), tipo,
            None, None, None, props.get("num_floors"), fonte, b["id"],
        ))
        add_predio(b["id"], geom, centro(geom), props.get("num_floors"), fonte, tipo, 0)

    osm_com_endereco = set(to_osm.values())
    overture_tree = strtree.STRtree(polys)
    for oi, o in enumerate(osm_features):
        geom = osm_polys[oi]
        if oi in osm_com_endereco or geom.is_empty:
            continue
        # OSM é só onde o Overture não cobre: sem isso o prédio sai em dobro.
        if len(overture_tree.query(geom, predicate="intersects")):
            continue
        pid = osm_id(oi)
        tipo = best_type(None, {"class": (o["properties"] or {}).get("building")})
        rows.append((
            pid, geom.wkt, _area_m2(geom), tipo,
            None, None, None, None, "OpenStreetMap", pid,
        ))
        add_predio(pid, geom, centro(geom), None, "OpenStreetMap", tipo, 0)

    predio_rows = [
        (pid, p["geom"].wkt, p["ponto"].wkt,
         _area_m2(p["geom"]), tipo_dominante(p["tipos"]), p["num_pav"],
         p["fonte"], p["n"])
        for pid, p in predios.items()
    ]
    return rows, predio_rows


def publicar(cur, tabelas=TABELAS):
    """Troca `{t}_new` por `{t}` num único RENAME (atômico no MySQL/MariaDB)."""
    cur.execute("DROP TABLE IF EXISTS " + ", ".join(f"{t}_old" for t in tabelas))
    pares, velhas = [], []
    for t in tabelas:
        cur.execute("SHOW TABLES LIKE %s", (t,))
        if cur.fetchone():
            pares.append(f"{t} TO {t}_old")
            velhas.append(f"{t}_old")
        pares.append(f"{t}_new TO {t}")
    cur.execute("RENAME TABLE " + ", ".join(pares))
    if velhas:
        cur.execute("DROP TABLE " + ", ".join(velhas))


def main():
    print("Lendo edificações do Overture...")
    building_features = load_buildings()
    print(f"  {len(building_features)} prédios")

    print("Lendo endereços do QG...")
    qg_features = load_qg_points()
    print(f"  {len(qg_features)} pontos de endereço")

    print("2ª fonte (OSM)...")
    osm_features = load_osm_buildings()
    print(f"  {len(osm_features)} polígonos OSM")

    print("Relacionando endereços x prédios (espacialmente)...")
    rows, predio_rows = montar(building_features, qg_features, osm_features)
    bolinhas = sum(1 for r in rows if r[8] == "QG/CNEFE")
    print(f"  {len(qg_features) - bolinhas} endereços em prédios, "
          f"{bolinhas} sem prédio; {len(predio_rows)} prédios no total")

    print("Gravando no MySQL...")
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS "
                        + ", ".join(f"{t}_new" for t in TABELAS))
            cur.execute(SCHEMA_BUILDINGS)
            cur.execute(SCHEMA_PREDIOS)

            # WKT: SRID 0 no MySQL 8 e no MariaDB (GeoJSON daria 4326 no MySQL 8).
            sql_rows = (
                "INSERT INTO buildings_new "
                "(id, geom, area_m2, tipo, endereco, bairro, estabelecimento, "
                "num_pavimentos, fonte, predio_id) "
                "VALUES (%s, ST_GeomFromText(%s), %s, %s, %s, %s, %s, %s, %s, %s)"
            )
            sql_predios = (
                "INSERT INTO predios_new "
                "(predio_id, geom, ponto, area_m2, tipo, num_pavimentos, fonte, n_enderecos) "
                "VALUES (%s, ST_GeomFromText(%s), ST_GeomFromText(%s), "
                "%s, %s, %s, %s, %s)"
            )
            CHUNK = 500
            for sql, batch in ((sql_rows, rows), (sql_predios, predio_rows)):
                for i in range(0, len(batch), CHUNK):
                    cur.executemany(sql, batch[i:i + CHUNK])
            conn.commit()
            publicar(cur)
            cur.execute("SELECT COUNT(*), SUM(tipo='desconhecido') FROM buildings")
            total, unknown = cur.fetchone()
            print(f"  Inseridos {total} registros em `buildings` "
                  f"({unknown} sem tipo identificado = desconhecido) "
                  f"e {len(predio_rows)} em `predios`")
    finally:
        conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
