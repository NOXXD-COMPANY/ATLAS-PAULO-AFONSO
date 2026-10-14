"""Conexão com o MySQL e consultas usadas pela API."""

import json

import pymysql

from .config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# 6 casas decimais = ~10 cm: sobra precisão e o JSON fica ~2x menor.
SELECT_FIELDS = (
    "id, ST_AsGeoJSON(geom, 6) AS geojson, area_m2, tipo, endereco, bairro, "
    "estabelecimento, num_pavimentos, fonte, predio_id"
)

SELECT_PREDIO_FIELDS = (
    "predio_id, ST_AsGeoJSON(geom, 6) AS geojson, ST_X(ponto) AS x, "
    "ST_Y(ponto) AS y, tipo, num_pavimentos, fonte, n_enderecos"
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
        clauses.append(f"bairro IN ({','.join(['%s'] * len(bairros))})")
        params.extend(bairros)
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
        # `<=>` compara NULL como valor: prédio sem fonte não some.
        clauses.append(
            "(NOT (fonte <=> %s) OR MBRIntersects(geom, ST_GeomFromText(%s)))")
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
    geometry = json.loads(row["geojson"])
    properties = {k: row[k] for k in (
        "id", "area_m2", "tipo", "endereco", "bairro",
        "estabelecimento", "num_pavimentos", "fonte", "predio_id",
    )}
    properties["tipo"] = properties["tipo"] or "desconhecido"
    return {
        "type": "Feature",
        "id": row["id"],
        "geometry": geometry,
        "properties": properties,
    }


def row_to_predio(row):
    """Feature mínima do mapa: polígono, cor, 3D e o ponto no centro."""
    return {
        "type": "Feature",
        "id": row["predio_id"],
        "geometry": json.loads(row["geojson"]),
        "properties": {
            "tipo": row["tipo"] or "desconhecido",
            "fonte": row["fonte"],
            "num_pavimentos": row["num_pavimentos"],
            "n": row["n_enderecos"],
            "ponto": [round(row["x"], 6), round(row["y"], 6)],
        },
    }


def fetch_all_buildings(bbox=None, bairros=None, tipo=None, fonte=None,
                         limit=None, offset=0, em_cobertura=False):
    with connect() as conn, conn.cursor() as cur:
        where, params = build_where(
            bbox=bbox, bairros=bairros, tipo=tipo, fonte=fonte,
            em_cobertura=em_cobertura)
        sql = f"SELECT {SELECT_FIELDS} FROM buildings {where} ORDER BY id".rstrip()
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params = list(params) + [int(limit), int(offset)]
        cur.execute(sql, params)
        return [row_to_feature(r) for r in cur.fetchall()]


def fetch_predios(limit, offset=0, em_cobertura=False):
    """Um feature por prédio (sem repetir o polígono por endereço)."""
    where, params = build_where(em_cobertura=em_cobertura)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {SELECT_PREDIO_FIELDS} FROM predios {where} "
            "ORDER BY predio_id LIMIT %s OFFSET %s",
            list(params) + [int(limit), int(offset)])
        return [row_to_predio(r) for r in cur.fetchall()]


def fetch_predio(predio_id: str):
    """Prédio com todos os endereços dele, ou None."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {SELECT_PREDIO_FIELDS}, area_m2 FROM predios "
            "WHERE predio_id = %s", (predio_id,))
        row = cur.fetchone()
        if row is None:
            return None
        enderecos = []
        if row["n_enderecos"]:
            cur.execute(
                "SELECT id, endereco, bairro, estabelecimento, tipo "
                "FROM buildings WHERE predio_id = %s ORDER BY endereco, id",
                (predio_id,))
            enderecos = cur.fetchall()
        feature = row_to_predio(row)
        feature["properties"]["area_m2"] = row["area_m2"]
        feature["properties"]["enderecos"] = enderecos
        return feature


def fetch_stats(bbox=None, bairros=None, tipo=None, fonte=None,
                em_cobertura=False):
    """Agregados (total, por tipo, por bairro, áreas) com os mesmos filtros."""
    where, params = build_where(
        bbox=bbox, bairros=bairros, tipo=tipo, fonte=fonte,
        em_cobertura=em_cobertura)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS n, COUNT(DISTINCT predio_id) AS predios "
            f"FROM buildings {where}".rstrip(), params)
        contagem = cur.fetchone()
        total = contagem["n"] or 0

        cur.execute(
            f"SELECT tipo, COUNT(*) AS n FROM buildings {where} GROUP BY tipo",
            params)
        by_tipo = {(r["tipo"] or "desconhecido"): r["n"] for r in cur.fetchall()}

        cur.execute(
            f"SELECT bairro, COUNT(*) AS n FROM buildings {where} GROUP BY bairro",
            params)
        by_bairro = {(r["bairro"] or "Não informado"): r["n"]
                      for r in cur.fetchall()}

        # Tabela cruzada: o relatório filtra tipo × bairro sem nova consulta.
        cur.execute(
            f"SELECT bairro, tipo, COUNT(*) AS n FROM buildings {where} "
            "GROUP BY bairro, tipo", params)
        by_bairro_tipo = [
            {"bairro": r["bairro"] or "Não informado",
             "tipo": r["tipo"] or "desconhecido", "n": r["n"]}
            for r in cur.fetchall()]

        cur.execute(
            f"SELECT SUM(area_m2) AS total, AVG(area_m2) AS media "
            f"FROM buildings {where}".rstrip(), params)
        areas = cur.fetchone()
        return {
            "total": total,
            "predios": contagem["predios"] or 0,
            "by_tipo": by_tipo,
            "by_bairro": by_bairro,
            "by_bairro_tipo": by_bairro_tipo,
            "area_total_m2": areas["total"],
            "area_media_m2": (float(areas["media"])
                              if areas["media"] is not None else None),
        }


def fetch_building(building_id: str):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {SELECT_FIELDS} FROM buildings WHERE id = %s", (building_id,))
        row = cur.fetchone()
        return row_to_feature(row) if row else None