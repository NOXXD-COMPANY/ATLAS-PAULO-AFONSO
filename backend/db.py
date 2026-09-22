"""Conexão com o MySQL e consultas usadas pela API."""

import json

import pymysql

from .config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

SELECT_FIELDS = (
    "id, ST_AsGeoJSON(geom), area_m2, tipo, endereco, bairro, "
    "estabelecimento, num_pavimentos, fonte"
)


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
    """Transforma uma linha da tabela `buildings` em uma Feature GeoJSON."""
    geometry = json.loads(row["ST_AsGeoJSON(geom)"])
    properties = {k: row[k] for k in (
        "id", "area_m2", "tipo", "endereco", "bairro",
        "estabelecimento", "num_pavimentos", "fonte",
    )}
    properties["tipo"] = properties["tipo"] or "desconhecido"
    return {
        "type": "Feature",
        "id": row["id"],
        "geometry": geometry,
        "properties": properties,
    }


def fetch_all_buildings():
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {SELECT_FIELDS} FROM buildings")
        return [row_to_feature(r) for r in cur.fetchall()]


def fetch_building(building_id: str):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {SELECT_FIELDS} FROM buildings WHERE id = %s", (building_id,))
        row = cur.fetchone()
        return row_to_feature(row) if row else None