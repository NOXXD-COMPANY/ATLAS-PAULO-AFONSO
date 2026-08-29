"""
Atlas Urbano de Paulo Afonso — Pipeline de Processamento de Dados

Etapas:
1. Carrega dados de edificações (Overture Maps) e endereços (CNEFE/IBGE).
2. Calcula área métrica real de telhado (m²) em SIRGAS 2000 / UTM Zone 24S (EPSG:31984).
3. Constrói índice espacial R-tree (STRtree).
4. Realiza o matching espacial com tolerâncias de hitbox (0m exato, buffer de 5m e 10m).
5. Enriquece as geometrias e exporta GeoJSONs e tabela de estatísticas por bairro.

Uso:
    python backend/processar_dados.py
"""

import json
import time
import os
import statistics
from collections import defaultdict
from shapely.geometry import shape, Point
from shapely.ops import transform
from shapely.strtree import STRtree
from shapely import prepare
import pyproj

# Diretórios base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

# Arquivos de entrada (raw data)
OVERTURE_INPUT = os.path.join(DATA_RAW_DIR, "overture", "edificacoes_overture.geojson")
CNFE_INPUT = os.path.join(DATA_RAW_DIR, "cnefe_json", "dados_cnfe.json")

# Arquivos de saída (processed data para consumo do frontend)
BUILDINGS_OUTPUT = os.path.join(DATA_PROCESSED_DIR, "edificacoes_com_cnfe.geojson")
POINTS_OUTPUT = os.path.join(DATA_PROCESSED_DIR, "cnfe_pontos.geojson")
STATS_OUTPUT = os.path.join(DATA_PROCESSED_DIR, "estatisticas_bairros.json")

ESPECIE_MAP = {
    "1": "Domicílio particular",
    "2": "Domicílio coletivo",
    "3": "Estabelecimento agropecuário",
    "4": "Estabelecimento de ensino",
    "5": "Estabelecimento de saúde",
    "6": "Estabelecimento religioso / outros",
    "7": "Edificação em construção / reforma",
    "8": "Estabelecimento de outro tipo",
}

def main():
    print("=" * 60)
    print("Atlas Urbano de Paulo Afonso — Processamento Espacial")
    print("=" * 60)

    # 1. Carregamento
    print("\n[1/5] Carregando arquivos GeoJSON / JSON...")
    t0 = time.time()
    with open(OVERTURE_INPUT, "r", encoding="utf-8") as f:
        overture = json.load(f)
    buildings = overture["features"]

    with open(CNFE_INPUT, "r", encoding="utf-8") as f:
        cnfe = json.load(f)
    points = cnfe["features"]
    print(f"      {len(buildings):,} edificações | {len(points):,} endereços ({time.time()-t0:.1f}s)")

    # 2. Projeção e Cálculo de Área em m² (EPSG:31984 - SIRGAS 2000 / UTM 24S)
    print("\n[2/5] Projetando geometrias e calculando área m² (EPSG:31984)...")
    t0 = time.time()
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:31984", always_xy=True).transform

    bld_geoms_wgs84 = []
    bld_geoms_utm = []
    for feat in buildings:
        g_wgs84 = shape(feat["geometry"])
        g_utm = transform(transformer, g_wgs84)
        feat["properties"]["area_m2"] = round(g_utm.area, 2)
        prepare(g_wgs84)
        prepare(g_utm)
        bld_geoms_wgs84.append(g_wgs84)
        bld_geoms_utm.append(g_utm)

    print(f"      Áreas calculadas em {time.time()-t0:.1f}s.")

    # 3. Índice espacial e matching
    #    Faz o matching em projeção métrica (UTM 24S) para distâncias corretas.
    #    Procura TODOS os edifícios dentro do raio de busca e associa ao verdadeiro
    #    mais próximo (distância geométrica ponto-polígono), maximizando o match.
    print("\n[3/5] Construindo índice espacial R-tree (métrico) e associando endereços...")
    t0 = time.time()
    tree_utm = STRtree(bld_geoms_utm)

    # Raio máximo de associação (metros). Guardamos a distância real; o usuário
    # escolhe a tolerância visual no mapa sem precisar reprocessar.
    SEARCH_RADIUS_M = 50.0
    bld_matches = [[] for _ in range(len(buildings))]

    for pt_feat in points:
        coords = pt_feat["geometry"]["coordinates"]
        pt_wgs84 = Point(coords[0], coords[1])
        pt_utm = transform(transformer, pt_wgs84)
        props = pt_feat["properties"]

        # 1) Ponto dentro de um polígono (0m)
        contained = tree_utm.query(pt_utm)
        matched_idx = None
        dist_m = 9999.0

        for idx in contained:
            if bld_geoms_utm[idx].contains(pt_utm):
                matched_idx = idx
                dist_m = 0.0
                break

        # 2) Fora: procura os edifícios cuja bbox cai dentro do buffer e
        #    mede a distância geométrica real de cada um, ficando com o mais próximo.
        if matched_idx is None:
            candidates = tree_utm.query(pt_utm.buffer(SEARCH_RADIUS_M))
            best_idx = None
            best_dist = float("inf")
            for idx in candidates:
                if bld_geoms_utm[idx].contains(pt_utm):
                    # caiu dentro no buffer de busca, mas não no teste acima — raro
                    d = 0.0
                else:
                    d = pt_utm.distance(bld_geoms_utm[idx])
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
            if best_idx is not None and best_dist <= SEARCH_RADIUS_M:
                matched_idx = best_idx
                dist_m = round(best_dist, 1)

        if matched_idx is not None:
            record = {
                "dist_m": dist_m,
                "endereco": props.get("LOGRAD_NUM", ""),
                "complemento": props.get("COMPLEMENTO", ""),
                "cep": props.get("CEP", ""),
                "localidade": props.get("DSC_LOCALIDADE", ""),
                "estabelecimento": props.get("DSC_ESTABELECIMENTO", ""),
                "especie": props.get("COD_ESPECIE", ""),
                "especie_desc": ESPECIE_MAP.get(str(props.get("COD_ESPECIE", "")), "Outro"),
                "setor": props.get("COD_SETOR", ""),
                "cod_endereco": props.get("COD_UNICO_ENDERECO", ""),
            }
            bld_matches[matched_idx].append(record)

        props["dist_to_building_m"] = dist_m
        props["matched_exact"] = (dist_m == 0.0)
        props["matched_buffer_5m"] = (dist_m <= 5.0)
        props["matched_buffer_10m"] = (dist_m <= 10.0)
        props["especie_desc"] = ESPECIE_MAP.get(str(props.get("COD_ESPECIE", "")), "Outro")

    # Enriquecimento das edificações
    for idx, feat in enumerate(buildings):
        records = bld_matches[idx]
        records.sort(key=lambda r: r["dist_m"])

        exact_list = [r for r in records if r["dist_m"] == 0.0]
        buf5_list  = [r for r in records if r["dist_m"] <= 5.0]
        buf10_list = [r for r in records if r["dist_m"] <= 10.0]

        feat["properties"]["cnfe_enderecos"] = records
        feat["properties"]["cnfe_count_exact"] = len(exact_list)
        feat["properties"]["cnfe_count_5m"] = len(buf5_list)
        feat["properties"]["cnfe_count_10m"] = len(buf10_list)
        feat["properties"]["cnfe_count"] = len(buf10_list)

        if records:
            first = records[0]
            feat["properties"]["cnfe_endereco_principal"] = first["endereco"]
            feat["properties"]["cnfe_localidade"] = first["localidade"]
            feat["properties"]["cnfe_cep"] = first["cep"]
            feat["properties"]["cnfe_dist_m"] = first["dist_m"]

    print(f"      Matching concluído em {time.time()-t0:.1f}s.")

    # 4. Salvar saídas
    print("\n[4/5] Salvando GeoJSONs processados...")
    with open(BUILDINGS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(overture, f, ensure_ascii=False)

    with open(POINTS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(cnfe, f, ensure_ascii=False)

    # 5. Agregação por Bairro
    print("\n[5/5] Gerando consolidação estatística por bairro...")
    bairros_stats = defaultdict(lambda: {
        "total_bld": 0,
        "area_total_m2": 0.0,
        "areas_m2": [],
        "total_enderecos_cnfe": 0,
        "domicilios": 0,
        "comercio_outros": 0,
        "saude": 0,
        "ensino": 0,
        "em_construcao": 0
    })

    for feat in buildings:
        p = feat["properties"]
        bairro = p.get("cnfe_localidade") or "ZONA RURAL / NÃO IDENTIFICADO"
        area = p.get("area_m2", 0)

        b = bairros_stats[bairro]
        b["total_bld"] += 1
        b["area_total_m2"] += area
        b["areas_m2"].append(area)

        for end in p.get("cnfe_enderecos", []):
            if end["dist_m"] <= 10.0:
                b["total_enderecos_cnfe"] += 1
                esp = str(end["especie"])
                if esp == "1": b["domicilios"] += 1
                elif esp == "4": b["ensino"] += 1
                elif esp == "5": b["saude"] += 1
                elif esp == "7": b["em_construcao"] += 1
                else: b["comercio_outros"] += 1

    tabela_bairros = []
    for nome, b in bairros_stats.items():
        mediana_m2 = round(statistics.median(b["areas_m2"]), 1) if b["areas_m2"] else 0
        tabela_bairros.append({
            "bairro": nome,
            "edificacoes": b["total_bld"],
            "area_total_m2": round(b["area_total_m2"], 1),
            "area_mediana_m2": mediana_m2,
            "enderecos_cnfe": b["total_enderecos_cnfe"],
            "domicilios": b["domicilios"],
            "ensino": b["ensino"],
            "saude": b["saude"],
            "em_construcao": b["em_construcao"],
        })

    tabela_bairros.sort(key=lambda x: x["edificacoes"], reverse=True)

    with open(STATS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(tabela_bairros, f, ensure_ascii=False, indent=2)

    print(f"      {len(tabela_bairros)} localidades salvas em {STATS_OUTPUT}")
    print("\nProcessamento concluído com sucesso!")

if __name__ == "__main__":
    main()
