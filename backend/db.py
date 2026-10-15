"""Conexão com o MySQL e consultas usadas pela API."""

import json
import hashlib
from concurrent.futures import CancelledError

import pymysql
from shapely.geometry import shape

from .config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

SELECT_FIELDS = (
    "id, ST_AsGeoJSON(geom), area_m2, tipo, endereco, bairro, "
    "estabelecimento, num_pavimentos, fonte"
)

SELECT_LIGHT_FIELDS = "id, ST_AsGeoJSON(geom), tipo, fonte, num_pavimentos"

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
    )


def row_to_feature(row):
    geometry_json = row["ST_AsGeoJSON(geom)"]
    geometry = json.loads(geometry_json)
    geometry_key = hashlib.sha1(geometry_json.encode("utf-8")).hexdigest()
    properties = {k: row[k] for k in (
        "id", "area_m2", "tipo", "endereco", "bairro",
        "estabelecimento", "num_pavimentos", "fonte",
    )}
    properties["tipo"] = properties["tipo"] or "desconhecido"
    properties["geometry_key"] = geometry_key
    return {
        "type": "Feature",
        "id": row["id"],
        "geometry": geometry,
        "properties": properties,
    }


def row_to_light_feature(row):
    """Feature mínima para renderizar o mapa (cor, filtro, 3D)."""
    geometry_json = row["ST_AsGeoJSON(geom)"]
    geometry = json.loads(geometry_json)
    geometry_key = hashlib.sha1(geometry_json.encode("utf-8")).hexdigest()
    return {
        "type": "Feature",
        "id": row["id"],
        "geometry": geometry,
        "properties": {
            "id": row["id"],
            "tipo": row.get("tipo") or "desconhecido",
            "fonte": row.get("fonte"),
            "num_pavimentos": row.get("num_pavimentos"),
            "geometry_key": geometry_key,
        },
    }


def fetch_all_buildings(bbox=None, bairros=None, tipo=None, fonte=None,
                         light=False, limit=None, offset=0, after_id=None,
                         em_cobertura=False):
    with connect() as conn, conn.cursor() as cur:
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


def fetch_building_tile(bounds, cancelled=None):
    """Busca footprints do tile e devolve features prontas para MVT."""
    where, params = build_where(bbox=bounds)
    if cancelled is not None and cancelled.is_set():
        raise CancelledError()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {SELECT_LIGHT_FIELDS} FROM buildings {where} ORDER BY id",
            params,
        )
        features = []
        seen_geometries = set()
        for row in cur.fetchall():
            if cancelled is not None and cancelled.is_set():
                raise CancelledError()
            geometry_json = row["ST_AsGeoJSON(geom)"]
            geometry_key = hashlib.sha1(geometry_json.encode("utf-8")).hexdigest()
            # Muitos endereços compartilham a mesma cobertura. O mapa 2D
            # precisa desenhar cada footprint uma vez; o detalhe continua
            # disponível pela rota individual.
            if geometry_key in seen_geometries:
                continue
            seen_geometries.add(geometry_key)
            features.append({
                "geometry": shape(json.loads(geometry_json)),
                "properties": {
                    "id": str(row["id"]),
                    "tipo": row.get("tipo") or "desconhecido",
                    "fonte": row.get("fonte") or "",
                    "num_pavimentos": row.get("num_pavimentos") or 0,
                    "geometry_key": geometry_key,
                },
            })
        return features


def fetch_stats(bbox=None, bairros=None, tipo=None, fonte=None,
                em_cobertura=False):
    """Agregados (total, por tipo, por bairro, áreas) com os mesmos filtros."""
    where, params = build_where(
        bbox=bbox, bairros=bairros, tipo=tipo, fonte=fonte,
        em_cobertura=em_cobertura)
    with connect() as conn, conn.cursor() as cur:
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
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {SELECT_FIELDS} FROM buildings WHERE id = %s", (building_id,))
        row = cur.fetchone()
        return row_to_feature(row) if row else None
