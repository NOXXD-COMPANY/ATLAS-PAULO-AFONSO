#!/usr/bin/env python3
"""Importa edificações (Overture/OSM) e endereços (QG/CNEFE) para o banco
de rascunho (DB_NAME_STAGE). Com --promover, copia o resultado para o banco
de produção (DB_NAME) numa única transação.

Rode sempre com: doppler run -- python import_data.py [--promover]
"""

import argparse
import json
import os
from collections import Counter

from shapely.geometry import Point, shape, mapping
from shapely import strtree

from backend.config import DB_NAME, DB_NAME_STAGE, SRID
from backend.db import connect

DATA_DIR = "data/raw"
OVERTURE_FILES = [
    f"{DATA_DIR}/overture/edificacoes_overture.geojson",
    f"{DATA_DIR}/overture/overture-2026-08-19.0-building--38.236,-9.410,-38.212,-9.395.geojson",
    f"{DATA_DIR}/overture/overture-2026-08-19.0-building-municipio.geojson",
]
# 2ª fonte (API aberta Overpass/OSM, sem login): fallback onde o Overture
# não tem polígono. Ausência do arquivo só desliga o fallback.
OSM_BUILDINGS = f"{DATA_DIR}/osm/osm_buildings_paulo_afonso.geojson"
MUNICIPIO_BOUNDARY = f"{DATA_DIR}/municipio_boundary.geojson"
QG_ENDERECOS = f"{DATA_DIR}/cnefe_json/dados_cnfe.json"
MUNICIPIO = "2924009"  # Paulo Afonso/BA

# ~15 m de tolerância na borda (ex.: porta na fachada, erro de GPS).
POINT_TOLERANCE_DEG = 0.000135
# shortcut: 1° ≈ 111.320 m sem corrigir pela latitude (erro < 2% em -9°),
# troque por distância geodésica se DISTANCIA_M virar critério de método.
METROS_POR_GRAU = 111320.0

NAO_INFORMADO = "Não informado"

# Pais antes de filhos: ordem de carga (e inversa para apagar).
TABELAS = [
    "FONTES", "BAIRROS", "LOCALIDADES", "EDIFICACOES", "EDIFICACAO_ORIGEM",
    "ENDERECOS", "ENDERECO_EDIFICACAO", "AGG_BAIRRO_TIPO",
]

GEO = f"ST_GeomFromGeoJSON(%s, 1, {SRID})"

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


def classify(qg_props, overture_props):
    """(tipo, ORIGEM_TIPO): CNEFE prevalece, depois subtype, depois class."""
    especie = (qg_props or {}).get("COD_ESPECIE")
    if especie in ESPECIE_TO_TIPO:
        return ESPECIE_TO_TIPO[especie], "cnefe"
    subtype = (overture_props or {}).get("subtype")
    if subtype in OVAERTURE_SUBTYPE_TO_TIPO:
        return OVAERTURE_SUBTYPE_TO_TIPO[subtype], "overture_subtype"
    cls = (overture_props or {}).get("class")
    if cls in OVERTURE_CLASS_TO_TIPO:
        return OVERTURE_CLASS_TO_TIPO[cls], "overture_class"
    return "desconhecido", "sem_dado"


def best_type(qg_props, overture_props):
    return classify(qg_props, overture_props)[0]


def polygon_of(feat):
    """Polígono válido do GeoJSON, ou None (o banco só aceita (MULTI)POLYGON)."""
    g = shape(feat["geometry"])
    if not g.is_valid:
        g = g.buffer(0)
    return g if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty else None


def match_points(polys, points, q_indices=None):
    """Associa pontos a polígonos: contém → tolerância de ~15 m → mais próximo.

    Retorna {índice do ponto: (índice do polígono, METODO, DISTANCIA_M)}.
    """
    tree = strtree.STRtree(polys)
    if q_indices is None:
        q_indices = range(len(points))
    point_to_poly = {}
    for qi in q_indices:
        x, y = points[qi]["geometry"]["coordinates"]
        pt = Point(x, y)
        # predicate testa ponto→polígono: "within", não "contains".
        hits = tree.query(pt, predicate="within")
        metodo = "contido"
        if len(hits) == 0:
            hits = tree.query(pt.buffer(POINT_TOLERANCE_DEG), predicate="intersects")
            metodo = "tolerancia"
        if len(hits) == 0:
            continue
        cands = [int(i) for i in hits]
        best = min(cands, key=lambda bi: pt.distance(polys[bi]))
        dist = 0.0 if metodo == "contido" else pt.distance(polys[best]) * METROS_POR_GRAU
        point_to_poly[qi] = (best, metodo, round(dist, 2))
    return point_to_poly


def fonte_principal(sources):
    """(nome, licença, confiança) do 1º dataset Overture; OSM se não houver."""
    s = dict(sources[0]) if sources else {}
    return (s.get("dataset") or "OpenStreetMap", s.get("license") or "ODbL-1.0",
            s.get("confidence"))


def montar_predios():
    """Lê as fontes e devolve (predios, qg_features, assoc).

    predios: dicts com geom, id_origem, fonte, licença, confiança, props.
    assoc: {índice do endereço: (índice do prédio, METODO, DISTANCIA_M)}.
    """
    print("Lendo edificações do Overture...")
    predios = []
    for b in load_buildings():
        g = polygon_of(b)
        if g is None:
            continue
        props = dict(b["properties"])
        sources = props.pop("sources", None) or []
        nome, licenca, conf = fonte_principal(sources)
        predios.append({"geom": g, "id_origem": b["id"], "fonte": nome,
                        "licenca": licenca, "confianca": conf,
                        "fontes": sources, "props": props,
                        "num_pav": props.get("num_floors")})
    n_overture = len(predios)
    print(f"  {n_overture} prédios")

    print("Lendo endereços do QG...")
    qg_features = load_qg_points()
    print(f"  {len(qg_features)} pontos de endereço")

    print("Relacionando endereços x prédios (espacialmente)...")
    assoc = match_points([p["geom"] for p in predios], qg_features) if predios else {}
    print(f"  {len(assoc)} endereços dentro de prédios")

    print("2ª fonte (OSM) para os endereços restantes...")
    osm = []
    for i, o in enumerate(load_osm_buildings()):
        g = polygon_of(o)
        if g is None:
            continue
        tags = o["properties"] or {}
        oid = str(tags.get("osm_id", i)).replace("/", "-")
        osm.append({"geom": g, "id_origem": f"osm-{oid}", "fonte": "OpenStreetMap",
                    "licenca": "ODbL-1.0", "confianca": None,
                    "fontes": [{"dataset": "OpenStreetMap"}],
                    "props": {**tags, "class": tags.get("building")},
                    "num_pav": None})
    unmatched = [qi for qi in range(len(qg_features)) if qi not in assoc]
    osm_match = match_points([p["geom"] for p in osm], qg_features, unmatched) if osm else {}
    for qi, (oi, metodo, dist) in osm_match.items():
        assoc[qi] = (n_overture + oi, metodo, dist)
    predios.extend(osm)
    print(f"  OSM: {len(osm)} polígonos, {len(osm_match)} endereços adotados")
    return predios, qg_features, assoc


def _num(v):
    return int(v) if v not in (None, "") else None


def gravar_stage(predios, qg_features, assoc):
    """Recarrega todas as tabelas do banco de rascunho a partir do zero."""
    arquivos = [p for p in OVERTURE_FILES + [OSM_BUILDINGS, MUNICIPIO_BOUNDARY, QG_ENDERECOS]
                if os.path.exists(p)]
    parametros = {"municipio": MUNICIPIO, "srid": SRID,
                  "point_tolerance_deg": POINT_TOLERANCE_DEG}

    # Bairro = DSC_LOCALIDADE do CNEFE (1:1) até haver malha oficial de bairros.
    localidades = {}
    for qf in qg_features:
        nome = qf["properties"].get("DSC_LOCALIDADE") or NAO_INFORMADO
        localidades.setdefault(nome, len(localidades) + 1)
    fontes = {}
    for p in predios:
        fontes.setdefault(p["fonte"], (len(fontes) + 1, p["licenca"]))

    tipos_do_predio = {}
    bairros_do_predio = {}
    for qi, (bi, _, _) in assoc.items():
        qp = qg_features[qi]["properties"]
        tipos_do_predio.setdefault(bi, []).append(classify(qp, None)[0])
        bairros_do_predio.setdefault(bi, []).append(
            localidades[qp.get("DSC_LOCALIDADE") or NAO_INFORMADO])

    edificacoes, origens = [], []
    for bi, p in enumerate(predios):
        tipos = tipos_do_predio.get(bi)
        if tipos:
            tipo, origem = Counter(tipos).most_common(1)[0][0], "cnefe"
            bairro_id = Counter(bairros_do_predio[bi]).most_common(1)[0][0]
        else:
            (tipo, origem), bairro_id = classify(None, p["props"]), None
        edificacoes.append((
            bi + 1, fontes[p["fonte"]][0], bairro_id, tipo, origem,
            int(len(set(tipos or [])) > 1), len(tipos or []), _num(p["num_pav"]),
            p["confianca"], json.dumps(mapping(p["geom"])),
            json.dumps(mapping(p["geom"].representative_point())),
        ))
        origens.append((bi + 1, p["id_origem"],
                        json.dumps(p["fontes"], ensure_ascii=False, default=str),
                        json.dumps(p["props"], ensure_ascii=False, default=str)))

    enderecos = []
    for qi, qf in enumerate(qg_features):
        qp = qf["properties"]
        enderecos.append((
            qi + 1, int(qp["COD_UNICO_ENDERECO"]), int(qp["COD_ESPECIE"]),
            _num(qp.get("COD_TIPO_ESPECI")), qp["COD_SETOR"],
            _num(qp.get("NUM_QUADRA")), _num(qp.get("NUM_FACE")), qp.get("CEP") or None,
            localidades[qp.get("DSC_LOCALIDADE") or NAO_INFORMADO],
            qp.get("LOGRAD_NUM") or "", qp.get("COMPLEMENTO") or None,
            qp.get("DSC_ESTABELECIMENTO") or None, int(qp["NV_GEO_COORD"]),
            json.dumps(qf["geometry"]),
        ))
    vinculos = [(qi + 1, bi + 1, metodo, dist) for qi, (bi, metodo, dist) in assoc.items()]

    inserts = [
        ("FONTES", "INSERT INTO FONTES (ID, NOME, LICENCA) VALUES (%s, %s, %s)",
         [(i, n, lic) for n, (i, lic) in fontes.items()]),
        ("BAIRROS", "INSERT INTO BAIRROS (ID, NOME) VALUES (%s, %s)",
         [(i, n) for n, i in localidades.items()]),
        ("LOCALIDADES", "INSERT INTO LOCALIDADES (ID, NOME, BAIRRO_ID) VALUES (%s, %s, %s)",
         [(i, n, i) for n, i in localidades.items()]),
        ("EDIFICACOES",
         "INSERT INTO EDIFICACOES (ID, FONTE_ID, BAIRRO_ID, TIPO_USO, ORIGEM_TIPO, "
         "USO_MISTO, N_ENDERECOS, NUM_PAVIMENTOS, CONFIANCA_FONTE, GEOM, PONTO_ROTULO) "
         f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, {GEO}, {GEO})", edificacoes),
        ("EDIFICACAO_ORIGEM",
         "INSERT INTO EDIFICACAO_ORIGEM (EDIFICACAO_ID, ID_ORIGEM, FONTES, ATRIBUTOS) "
         "VALUES (%s, %s, %s, %s)", origens),
        ("ENDERECOS",
         "INSERT INTO ENDERECOS (ID, COD_UNICO, COD_ESPECIE, COD_TIPO_ESPECI, COD_SETOR, "
         "NUM_QUADRA, NUM_FACE, CEP, LOCALIDADE_ID, LOGRADOURO_NUM, COMPLEMENTO, "
         "ESTABELECIMENTO, NV_GEO_COORD, PT) "
         f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, {GEO})", enderecos),
        ("ENDERECO_EDIFICACAO",
         "INSERT INTO ENDERECO_EDIFICACAO (ENDERECO_ID, EDIFICACAO_ID, METODO, DISTANCIA_M) "
         "VALUES (%s, %s, %s, %s)", vinculos),
    ]

    print(f"Gravando no banco de rascunho ({len(edificacoes)} prédios, "
          f"{len(enderecos)} endereços)...")
    conn = connect(DB_NAME_STAGE)
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for t in TABELAS + ["CARGAS"]:
                cur.execute(f"TRUNCATE TABLE {t}")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            cur.execute("INSERT INTO CARGAS (PARAMETROS, ARQUIVOS) VALUES (%s, %s)",
                        (json.dumps(parametros), json.dumps(arquivos)))
            carga_id = cur.lastrowid
            for tabela, sql, rows in inserts:
                # pymysql só agrupa executemany com %s puros no VALUES; com
                # ST_GeomFromGeoJSON(%s) seria 1 ida ao banco por linha.
                head, tpl = sql.split(" VALUES ")
                for i in range(0, len(rows), 500):
                    chunk = rows[i:i + 500]
                    cur.execute(f"{head} VALUES " + ",".join([tpl] * len(chunk)),
                                [v for r in chunk for v in r])
                print(f"  {tabela}: {len(rows)}")
            cur.execute(
                "INSERT INTO AGG_BAIRRO_TIPO (BAIRRO_NOME, TIPO_USO, N_EDIFICACOES, "
                "N_ENDERECOS, AREA_SOMA_M2) "
                "SELECT COALESCE(B.NOME, %s), E.TIPO_USO, COUNT(*), SUM(E.N_ENDERECOS), "
                "COALESCE(SUM(E.AREA_M2), 0) FROM EDIFICACOES E "
                "LEFT JOIN BAIRROS B ON B.ID = E.BAIRRO_ID GROUP BY 1, 2", (NAO_INFORMADO,))
            contagens = {t: len(rows) for t, _, rows in inserts}
            cur.execute("SELECT SUM(TIPO_USO = 'desconhecido') AS n FROM EDIFICACOES")
            contagens["EDIFICACOES_DESCONHECIDO"] = int(cur.fetchone()["n"] or 0)
            cur.execute("UPDATE CARGAS SET CONCLUIDA_EM = NOW(), CONTAGENS = %s WHERE ID = %s",
                        (json.dumps(contagens), carga_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"  Carga concluída: {contagens}")


def colunas_gravaveis(cur, tabela):
    """Colunas não geradas (AREA_M2 e ENDERECOS.TIPO_USO são calculadas)."""
    cur.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s "
        "AND TABLE_NAME = %s AND GENERATION_EXPRESSION = '' ORDER BY ORDINAL_POSITION",
        (DB_NAME_STAGE, tabela))
    return ", ".join(r["COLUMN_NAME"] for r in cur.fetchall())


def promover():
    """Substitui os dados de produção pelos do rascunho, tudo ou nada."""
    stage = f"`{DB_NAME_STAGE}`"
    conn = connect(DB_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {stage}.EDIFICACOES")
            n = cur.fetchone()["n"]
            cur.execute(f"SELECT COUNT(*) AS n FROM {stage}.CARGAS WHERE CONCLUIDA_EM IS NOT NULL")
            if not n or not cur.fetchone()["n"]:
                raise SystemExit("Rascunho vazio ou carga incompleta: produção intacta.")
            print(f"Promovendo {n} prédios do rascunho para produção...")
            for t in reversed(TABELAS):
                cur.execute(f"DELETE FROM {t}")
            for t in TABELAS:
                cols = colunas_gravaveis(cur, t)
                cur.execute(f"INSERT INTO {t} ({cols}) SELECT {cols} FROM {stage}.{t}")
            # Produção guarda o histórico de cargas; o ID é o dela.
            cols = "INICIADA_EM, CONCLUIDA_EM, PARAMETROS, ARQUIVOS, CONTAGENS"
            cur.execute(f"INSERT INTO CARGAS ({cols}) SELECT {cols} FROM {stage}.CARGAS")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("  Produção atualizada.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--promover", action="store_true",
                    help="após carregar o rascunho, substitui os dados de produção")
    args = ap.parse_args()
    if not (DB_NAME and DB_NAME_STAGE) or DB_NAME == DB_NAME_STAGE:
        raise SystemExit("DB_NAME e DB_NAME_STAGE ausentes ou iguais: use doppler run --")
    gravar_stage(*montar_predios())
    if args.promover:
        promover()
    print("Done.")


if __name__ == "__main__":
    main()
