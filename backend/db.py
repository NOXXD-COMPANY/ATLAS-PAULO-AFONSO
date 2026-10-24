"""Conexão com o MySQL e consultas usadas pela API."""

import json

import pymysql

from .config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, SRID

FROM_EDIFICACOES = (
    "FROM EDIFICACOES E JOIN FONTES F ON F.ID = E.FONTE_ID "
    "LEFT JOIN BAIRROS B ON B.ID = E.BAIRRO_ID"
)

# Endereço/estabelecimento exibidos: o primeiro endereço associado ao prédio.
_DO_PRIMEIRO_ENDERECO = (
    "(SELECT EN.{col} FROM ENDERECO_EDIFICACAO EE "
    "JOIN ENDERECOS EN ON EN.ID = EE.ENDERECO_ID "
    "WHERE EE.EDIFICACAO_ID = E.ID AND EN.{col} IS NOT NULL "
    "ORDER BY EN.ID LIMIT 1)"
)

SELECT_FIELDS = (
    "CAST(E.ID AS CHAR) AS id, ST_AsGeoJSON(E.GEOM) AS geojson, "
    "CAST(E.AREA_M2 AS DOUBLE) AS area_m2, E.TIPO_USO AS tipo, "
    f"{_DO_PRIMEIRO_ENDERECO.format(col='LOGRADOURO_NUM')} AS endereco, "
    "B.NOME AS bairro, "
    f"{_DO_PRIMEIRO_ENDERECO.format(col='ESTABELECIMENTO')} AS estabelecimento, "
    "E.NUM_PAVIMENTOS AS num_pavimentos, F.NOME AS fonte"
)

SELECT_LIGHT_FIELDS = (
    "CAST(E.ID AS CHAR) AS id, ST_AsGeoJSON(E.GEOM) AS geojson, "
    "E.TIPO_USO AS tipo, F.NOME AS fonte, E.NUM_PAVIMENTOS AS num_pavimentos"
)

MAX_LIMIT = 20000


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


def build_where(bbox=None, bairros=None, tipo=None, fonte=None):
    """Monta (cláusula WHERE, params) a partir dos filtros opcionais.

    O filtro espacial usa MBRIntersects para aproveitar o SPATIAL INDEX.
    O WKT vem em lon/lat; o SRID 4674 é lat/lon por padrão, daí o axis-order.
    Sem filtros retorna ("", []).
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
        clauses.append(
            "MBRIntersects(E.GEOM, ST_GeomFromText(%s, "
            f"{SRID}, 'axis-order=long-lat'))")
        params.append(wkt)
    if bairros:
        clauses.append(f"B.NOME IN ({','.join(['%s'] * len(bairros))})")
        params.extend(bairros)
    if tipo:
        clauses.append("E.TIPO_USO = %s")
        params.append(tipo)
    if fonte:
        clauses.append("F.NOME = %s")
        params.append(fonte)
    if not clauses:
        return ("", [])
    return ("WHERE " + " AND ".join(clauses), params)


def connect(database=DB_NAME):
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def row_to_feature(row):
    geometry = json.loads(row["geojson"])
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


def row_to_light_feature(row):
    """Feature mínima para renderizar o mapa (cor, filtro, 3D)."""
    geometry = json.loads(row["geojson"])
    return {
        "type": "Feature",
        "id": row["id"],
        "geometry": geometry,
        "properties": {
            "tipo": row.get("tipo") or "desconhecido",
            "fonte": row.get("fonte"),
            "num_pavimentos": row.get("num_pavimentos"),
        },
    }


def fetch_all_buildings(bbox=None, bairros=None, tipo=None, fonte=None,
                         light=False, limit=None, offset=0):
    with connect() as conn, conn.cursor() as cur:
        fields = SELECT_LIGHT_FIELDS if light else SELECT_FIELDS
        converter = row_to_light_feature if light else row_to_feature
        where, params = build_where(
            bbox=bbox, bairros=bairros, tipo=tipo, fonte=fonte)
        sql = f"SELECT {fields} {FROM_EDIFICACOES} {where} ORDER BY E.ID"
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params = list(params) + [int(limit), int(offset)]
        cur.execute(sql, params)
        return [converter(r) for r in cur.fetchall()]


def fetch_stats(bbox=None, bairros=None, tipo=None, fonte=None):
    """Agregados (total, por tipo, por bairro, áreas) com os mesmos filtros."""
    where, params = build_where(
        bbox=bbox, bairros=bairros, tipo=tipo, fonte=fonte)
    base = f"{FROM_EDIFICACOES} {where}"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n, CAST(SUM(E.AREA_M2) AS DOUBLE) AS total, "
            f"CAST(AVG(E.AREA_M2) AS DOUBLE) AS media {base}", params)
        totais = cur.fetchone()

        cur.execute(
            f"SELECT E.TIPO_USO AS tipo, COUNT(*) AS n {base} GROUP BY E.TIPO_USO",
            params)
        by_tipo = {(r["tipo"] or "desconhecido"): r["n"] for r in cur.fetchall()}

        cur.execute(
            f"SELECT B.NOME AS bairro, COUNT(*) AS n {base} GROUP BY B.NOME",
            params)
        by_bairro = {(r["bairro"] or "Não informado"): r["n"]
                      for r in cur.fetchall()}

        return {
            "total": totais["n"] or 0,
            "by_tipo": by_tipo,
            "by_bairro": by_bairro,
            "area_total_m2": totais["total"],
            "area_media_m2": totais["media"],
        }


def fetch_building(building_id: str):
    if not building_id.isdigit():  # ID é inteiro; evita cast implícito do MySQL
        return None
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {SELECT_FIELDS} {FROM_EDIFICACOES} WHERE E.ID = %s",
            (int(building_id),))
        row = cur.fetchone()
        return row_to_feature(row) if row else None
