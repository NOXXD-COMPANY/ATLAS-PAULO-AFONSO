"""Conexão com o MySQL e consultas usadas pela API."""

import json
import queue
from concurrent.futures import CancelledError
from contextlib import contextmanager

import pymysql
import shapely

from .config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# Identifica footprints iguais (vários endereços no mesmo prédio). O hash do
# WKB sai quase de graça no banco; o do GeoJSON custava mais que a consulta.
GEOMETRY_KEY = "SHA1(ST_AsBinary(geom)) AS geometry_key"

SELECT_FIELDS = (
    f"id, ST_AsGeoJSON(geom), {GEOMETRY_KEY}, area_m2, tipo, endereco, "
    "bairro, estabelecimento, num_pavimentos, fonte"
)

SELECT_LIGHT_FIELDS = (
    f"id, ST_AsGeoJSON(geom), {GEOMETRY_KEY}, tipo, fonte, num_pavimentos"
)

# WKB é bem mais barato de transferir e decodificar que GeoJSON.
TILE_FIELDS = (
    f"id, ST_AsBinary(geom) AS wkb, {GEOMETRY_KEY}, tipo, fonte, num_pavimentos, area_m2"
)

MAX_LIMIT = 20000

# Cobertura com polígonos: todo o município (Overture janela + arquivo
# município, recortados no contorno). Fora dela só existem bolinhas.
# Quando as fontes mudarem, atualize aqui.
JANELA_COBERTURA = (-38.5489, -9.7125, -37.9996, -9.3529)


def parse_bbox(raw):
    """Valida `minLng,minLat,maxLng,maxLat` → tupla de floats.

    Retorna None se raw for None. Levanta ValueError se inválido.
    """
    if raw is None:
        return None
    try:
        parts = [float(x) for x in raw.split(",")]
    except (ValueError, AttributeError):
        raise ValueError(f"bbox inválido: {raw!r}")
    if len(parts) != 4:
        raise ValueError(f"bbox inválido: {raw!r}")
    min_lng, min_lat, max_lng, max_lat = parts
    if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180):
        raise ValueError(f"bbox inválido: {raw!r}")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise ValueError(f"bbox inválido: {raw!r}")
    if not (min_lng < max_lng and min_lat < max_lat):
        raise ValueError(f"bbox inválido: {raw!r}")
    return (min_lng, min_lat, max_lng, max_lat)


def build_where(bbox=None, bairros=None, tipo=None, fonte=None,
                em_cobertura=False):
    """Monta (cláusula WHERE, params) a partir dos filtros opcionais.

    O filtro espacial usa MBRIntersects para aproveitar o SPATIAL INDEX.
    `em_cobertura=True` esconde as bolinhas fora da janela com polígonos
    (elas continuam no banco). Sem filtros retorna ("", []).
    """
    clauses = []
    params = []
    if bbox is not None:
        min_lng, min_lat, max_lng, max_lat = bbox
        wkt = (
            f"POLYGON(({min_lng} {min_lat},{max_lng} {min_lat},"
            f"{max_lng} {max_lat},{min_lng} {max_lat},"
            f"{min_lng} {min_lat}))"
        )
        clauses.append("MBRIntersects(geom, ST_GeomFromText(%s))")
        params.append(wkt)
    if bairros:
        sem_bairro = "Não informado" in bairros
        bairros_validos = [b for b in bairros if b != "Não informado"]
        bairro_clauses = []
        if bairros_validos:
            bairro_clauses.append(f"bairro IN ({','.join(['%s'] * len(bairros_validos))})")
            params.extend(bairros_validos)
        if sem_bairro:
            bairro_clauses.append("(bairro IS NULL OR bairro = '' OR bairro = %s)")
            params.append("Não informado")
        clauses.append("(" + " OR ".join(bairro_clauses) + ")")
    if tipo:
        clauses.append("tipo = %s")
        params.append(tipo)
    if fonte:
        clauses.append("fonte = %s")
        params.append(fonte)
    if em_cobertura:
        min_lng, min_lat, max_lng, max_lat = JANELA_COBERTURA
        wkt = (
            f"POLYGON(({min_lng} {min_lat},{max_lng} {min_lat},"
            f"{max_lng} {max_lat},{min_lng} {max_lat},"
            f"{min_lng} {min_lat}))"
        )
        clauses.append("(fonte != %s OR MBRIntersects(geom, ST_GeomFromText(%s)))")
        params.extend(["QG/CNEFE", wkt])
    if not clauses:
        return ("", [])
    return ("WHERE " + " AND ".join(clauses), params)


def connect():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        # Sem transação aberta entre pedidos: uma conexão reaproveitada
        # precisa enxergar uma reimportação feita depois.
        autocommit=True,
    )


_idle_connections = queue.LifoQueue(maxsize=8)


@contextmanager
def connection():
    """Conexão reaproveitada entre pedidos (abrir uma custa ~45 ms)."""
    try:
        conn = _idle_connections.get_nowait()
        conn.ping(reconnect=True)
    except queue.Empty:
        conn = connect()
    try:
        yield conn
    except BaseException:
        conn.close()
        raise
    try:
        _idle_connections.put_nowait(conn)
    except queue.Full:
        conn.close()


def close_idle_connections():
    while True:
        try:
            _idle_connections.get_nowait().close()
        except queue.Empty:
            return


def row_to_feature(row):
    geometry = json.loads(row["ST_AsGeoJSON(geom)"])
    properties = {k: row[k] for k in (
        "id", "area_m2", "tipo", "endereco", "bairro",
        "estabelecimento", "num_pavimentos", "fonte",
    )}
    properties["tipo"] = properties["tipo"] or "desconhecido"
    properties["geometry_key"] = row["geometry_key"]
    return {
        "type": "Feature",
        "id": row["id"],
        "geometry": geometry,
        "properties": properties,
    }


def row_to_light_feature(row):
    """Feature mínima para renderizar o mapa (cor, filtro, 3D)."""
    geometry = json.loads(row["ST_AsGeoJSON(geom)"])
    return {
        "type": "Feature",
        "id": row["id"],
        "geometry": geometry,
        "properties": {
            "id": row["id"],
            "tipo": row.get("tipo") or "desconhecido",
            "fonte": row.get("fonte"),
            "num_pavimentos": row.get("num_pavimentos"),
            "geometry_key": row["geometry_key"],
        },
    }


def fetch_all_buildings(bbox=None, bairros=None, tipo=None, fonte=None,
                         light=False, limit=None, offset=0, after_id=None,
                         em_cobertura=False):
    with connection() as conn, conn.cursor() as cur:
        fields = SELECT_LIGHT_FIELDS if light else SELECT_FIELDS
        converter = row_to_light_feature if light else row_to_feature
        where, params = build_where(
            bbox=bbox, bairros=bairros, tipo=tipo, fonte=fonte,
            em_cobertura=em_cobertura)
        if after_id is not None:
            where += (" AND " if where else "WHERE ") + "id > %s"
            params.append(after_id)
        sql = f"SELECT {fields} FROM buildings {where} ORDER BY id".rstrip()
        if limit is not None:
            sql += " LIMIT %s"
            params.append(int(limit))
            if after_id is None:
                sql += " OFFSET %s"
                params.append(int(offset))
        cur.execute(sql, params)
        return [converter(r) for r in cur.fetchall()]


SEARCH_FIELDS = ("endereco", "estabelecimento", "bairro")
MAX_SEARCH_TERMS = 6


def _like_escape(term):
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_search_where(query):
    """Cada palavra precisa aparecer em algum campo (endereço, estabelecimento
    ou bairro). A collation da tabela já ignora acento e caixa."""
    terms = query.split()[:MAX_SEARCH_TERMS]
    clauses, params = [], []
    for term in terms:
        pattern = f"%{_like_escape(term)}%"
        clauses.append("(" + " OR ".join(f"{field} LIKE %s" for field in SEARCH_FIELDS) + ")")
        params.extend([pattern] * len(SEARCH_FIELDS))
    return " AND ".join(clauses), params


def search(query, limit=8):
    """Prédios e bairros que batem com a busca, com um ponto para o mapa ir até lá."""
    where, params = build_search_where(query)
    if not where:
        return {"buildings": [], "bairros": []}
    prefix = f"{_like_escape(query.strip())}%"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, endereco, bairro, estabelecimento, tipo, "
            "ST_X(ST_Centroid(geom)) AS lng, ST_Y(ST_Centroid(geom)) AS lat "
            f"FROM buildings WHERE {where} "
            "AND (endereco IS NOT NULL OR estabelecimento IS NOT NULL) "
            # Quem começa com o texto digitado vem primeiro.
            "ORDER BY (estabelecimento LIKE %s OR endereco LIKE %s) DESC, endereco "
            "LIMIT %s",
            [*params, prefix, prefix, int(limit)],
        )
        buildings = [
            {**row, "tipo": row["tipo"] or "desconhecido",
             "lng": float(row["lng"]), "lat": float(row["lat"])}
            for row in cur.fetchall()
        ]
        terms = query.split()[:MAX_SEARCH_TERMS]
        cur.execute(
            "SELECT bairro, COUNT(*) AS total, "
            "AVG(ST_X(ST_Centroid(geom))) AS lng, AVG(ST_Y(ST_Centroid(geom))) AS lat "
            "FROM buildings WHERE "
            + " AND ".join(["bairro LIKE %s"] * len(terms))
            + " GROUP BY bairro ORDER BY total DESC LIMIT 4",
            [f"%{_like_escape(t)}%" for t in terms],
        )
        bairros = [
            {"bairro": row["bairro"], "total": int(row["total"]),
             "lng": float(row["lng"]), "lat": float(row["lat"])}
            for row in cur.fetchall()
        ]
    return {"buildings": buildings, "bairros": bairros}


def fetch_building_addresses(building_id):
    """Todos os endereços que dividem o footprint deste prédio."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT o.id, o.endereco, o.estabelecimento, o.tipo FROM buildings t "
            "JOIN buildings o ON MBRIntersects(o.geom, t.geom) AND ST_Equals(o.geom, t.geom) "
            "WHERE t.id = %s ORDER BY o.endereco, o.id LIMIT 100",
            (building_id,),
        )
        return [{**row, "tipo": row["tipo"] or "desconhecido"} for row in cur.fetchall()]


def fetch_data_version():
    """Muda a cada importação: o import_data.py recria a tabela."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT UNIX_TIMESTAMP(CREATE_TIME) AS created "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'buildings'"
        )
        row = cur.fetchone()
    return str(int(row["created"])) if row and row["created"] is not None else "0"


def fetch_centroids():
    """Um ponto por footprint; endereços no mesmo prédio contam uma vez."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT ST_X(ST_Centroid(geom)) AS x, ST_Y(ST_Centroid(geom)) AS y, "
            f"tipo, fonte, {GEOMETRY_KEY} FROM buildings ORDER BY id"
        )
        rows = cur.fetchall()
    unique = {}
    for row in rows:
        unique.setdefault(row["geometry_key"], row)
    return list(unique.values())


def fetch_building_tile(bounds, cancelled=None):
    """Busca footprints do tile e devolve features prontas para MVT."""
    where, params = build_where(bbox=bounds)
    if cancelled is not None and cancelled.is_set():
        raise CancelledError()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {TILE_FIELDS} FROM buildings {where} ORDER BY id",
            params,
        )
        rows = cur.fetchall()
    if cancelled is not None and cancelled.is_set():
        raise CancelledError()
    # Muitos endereços compartilham a mesma cobertura. O mapa 2D precisa
    # desenhar cada footprint uma vez; o detalhe continua disponível pela
    # rota individual.
    unique = {}
    for row in rows:
        unique.setdefault(row["geometry_key"], row)
    rows = list(unique.values())
    geometries = shapely.from_wkb([row["wkb"] for row in rows])
    return [
        {
            "geometry": geometry,
            "properties": {
                "id": str(row["id"]),
                "tipo": row.get("tipo") or "desconhecido",
                "fonte": row.get("fonte") or "",
                "num_pavimentos": row.get("num_pavimentos") or 0,
                # O ponto da visão intermediária tem a mesma área do prédio.
                "area_m2": float(row.get("area_m2") or 0),
                "geometry_key": row["geometry_key"],
            },
        }
        for row, geometry in zip(rows, geometries)
    ]


def fetch_stats(bbox=None, bairros=None, tipo=None, fonte=None,
                em_cobertura=False):
    """Agregados (total, por tipo, por bairro, áreas) com os mesmos filtros."""
    where, params = build_where(
        bbox=bbox, bairros=bairros, tipo=tipo, fonte=fonte,
        em_cobertura=em_cobertura)
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM buildings {where}".rstrip(),
                    params)
        total = cur.fetchone()["n"] or 0

        cur.execute(
            f"SELECT tipo, COUNT(*) AS n FROM buildings {where} GROUP BY tipo",
            params)
        by_tipo = {(r["tipo"] or "desconhecido"): r["n"] for r in cur.fetchall()}

        cur.execute(
            f"SELECT bairro, COUNT(*) AS n FROM buildings {where} GROUP BY bairro",
            params)
        by_bairro = {(r["bairro"] or "Não informado"): r["n"]
                      for r in cur.fetchall()}

        cur.execute(
            f"SELECT SUM(area_m2) AS total, AVG(area_m2) AS media "
            f"FROM buildings {where}".rstrip(), params)
        areas = cur.fetchone()
        return {
            "total": total,
            "by_tipo": by_tipo,
            "by_bairro": by_bairro,
            "area_total_m2": areas["total"],
            "area_media_m2": (float(areas["media"])
                              if areas["media"] is not None else None),
        }


def fetch_building(building_id: str):
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {SELECT_FIELDS} FROM buildings WHERE id = %s", (building_id,))
        row = cur.fetchone()
        return row_to_feature(row) if row else None
