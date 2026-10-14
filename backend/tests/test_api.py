"""Testes essenciais (P6): só pontos críticos, sem cobertura completa.

Roda com: ./.venv/bin/python -m pytest backend/tests -q
(dependências de dev: pip install -r backend/requirements-dev.txt)
"""

import pytest

from backend import db


# --- P1: construção/validação do BBOX -------------------------------------

def test_parse_bbox_valido():
    assert db.parse_bbox("-38.24,-9.41,-38.21,-9.39") == (
        -38.24, -9.41, -38.21, -9.39)


def test_parse_bbox_none():
    assert db.parse_bbox(None) is None


@pytest.mark.parametrize("raw", [
    "a,b,c,d", "1,2,3", "1,2,3,4,5", "",
    "-38.21,-9.41,-38.24,-9.39",  # min > max
    "0,0,0,0",
    "-200,0,10,0", "0,-100,10,0",  # fora do planeta
    "-38.24,-9.41,-38.21",  # faltando número
])
def test_parse_bbox_invalido_rejeita(raw):
    with pytest.raises(ValueError):
        db.parse_bbox(raw)


# --- P2: filtros combinados (builder puro, sem banco) -----------------------

def test_build_where_vazio():
    assert db.build_where() == ("", [])


def test_build_where_bbox_usa_indice_espacial():
    clause, params = db.build_where(bbox=(-38.24, -9.41, -38.21, -9.39))
    assert "MBRIntersects(geom, ST_GeomFromText(%s))" in clause
    assert params[0].startswith("POLYGON((")


def test_build_where_combina_tudo_na_ordem():
    clause, params = db.build_where(
        bbox=(-38.24, -9.41, -38.21, -9.39),
        bairros=["CENTRO", "BNH"],
        tipo="comercial",
        fonte="QG/CNEFE",
    )
    assert clause.startswith("WHERE ")
    assert "AND" in clause
    assert params[1:] == ["CENTRO", "BNH", "comercial", "QG/CNEFE"]


def test_build_where_apenas_bairro():
    clause, params = db.build_where(bairros=["CENTRO"])
    assert clause == "WHERE bairro IN (%s)"
    assert params == ["CENTRO"]


# --- P3: conversão para GeoJSON ---------------------------------------------

def _row(full=True):
    base = {"geojson": '{"type":"Point","coordinates":[-38.2,-9.4]}'}
    if full:
        base.update({
            "id": "x1", "area_m2": 112.5, "tipo": None, "endereco": "Rua A",
            "bairro": "CENTRO", "estabelecimento": None,
            "num_pavimentos": 2, "fonte": "QG/CNEFE", "predio_id": "x1",
        })
    else:
        base.update({"predio_id": "p1", "tipo": None, "fonte": "OSM",
                     "num_pavimentos": None, "n_enderecos": 3,
                     "x": -38.2000004, "y": -9.4})
    return base


def test_row_to_feature_normaliza_tipo():
    f = db.row_to_feature(_row())
    assert f["type"] == "Feature"
    assert f["properties"]["tipo"] == "desconhecido"  # None → fallback
    assert f["geometry"]["type"] == "Point"
    assert f["properties"]["predio_id"] == "x1"


def test_row_to_predio_minimo():
    f = db.row_to_predio(_row(full=False))
    assert f["id"] == "p1"
    assert f["properties"] == {"tipo": "desconhecido", "fonte": "OSM",
                               "num_pavimentos": None, "n": 3,
                               "ponto": [-38.2, -9.4]}


# --- Classificação best_type (regra de domínio do ETL) ----------------------

def test_best_type_qg_prevalece():
    import import_data
    assert import_data.best_type({"COD_ESPECIE": "6"}, {"subtype": "x"}) == "comercial"
    assert import_data.best_type({"COD_ESPECIE": "7"}, {}) == "desconhecido"
    assert import_data.best_type({}, {"subtype": "residential"}) == "residencial"
    assert import_data.best_type({}, {"class": "church"}) == "religioso"
    assert import_data.best_type({}, {}) == "desconhecido"
    assert import_data.best_type(None, None) == "desconhecido"


# --- Endpoints principais (db mockado: sem banco) ---------------------------

@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient
    import backend.main as main

    vistas = {}

    def fake_list(**kwargs):
        vistas.update(kwargs)
        return [{"type": "Feature", "id": "a",
                 "geometry": {"type": "Point", "coordinates": [0, 0]},
                 "properties": {"tipo": "residencial", "fonte": None,
                                "num_pavimentos": None}}]

    monkeypatch.setattr(main.db, "fetch_all_buildings", fake_list)
    monkeypatch.setattr(main.db, "fetch_stats",
                        lambda **k: {"total": 1, "by_tipo": {},
                                     "by_bairro": {}, "area_total_m2": None,
                                     "area_media_m2": None})
    monkeypatch.setattr(main.db, "fetch_building", lambda i: None)

    def fake_predios(**kwargs):
        vistas["predios"] = kwargs
        return []

    monkeypatch.setattr(main.db, "fetch_predios", fake_predios)
    monkeypatch.setattr(main.db, "fetch_predio", lambda i: None)
    return TestClient(main.app), vistas


def test_list_passa_bbox_e_filtros(client):
    t, vistas = client
    r = t.get("/api/buildings", params={
        "bbox": "-38.24,-9.41,-38.21,-9.39",
        "bairro": ["CENTRO", "BNH"], "tipo": "residencial"})
    assert r.status_code == 200
    assert vistas["bbox"] == (-38.24, -9.41, -38.21, -9.39)
    assert vistas["bairros"] == ["CENTRO", "BNH"]
    assert vistas["tipo"] == "residencial"
    assert r.json()["features"][0]["properties"]["tipo"] == "residencial"


def test_list_bbox_invalido_422(client):
    t, _ = client
    r = t.get("/api/buildings", params={"bbox": "a,b,c,d"})
    assert r.status_code == 422


def test_detail_404_mantido(client):
    t, _ = client
    r = t.get("/api/buildings/nao-existe")
    assert r.status_code == 404
    assert r.json() == {"detail": "building not found"}


def test_predios_pagina_e_cobertura(client):
    t, vistas = client
    r = t.get("/api/predios", params={"em_cobertura": "true",
                                      "limit": 100, "offset": 200})
    assert r.status_code == 200
    assert r.json()["features"] == []
    assert vistas["predios"] == {"limit": 100, "offset": 200,
                                 "em_cobertura": True}


def test_predios_limite_acima_do_maximo_422(client):
    t, _ = client
    r = t.get("/api/predios", params={"limit": db.MAX_LIMIT + 1})
    assert r.status_code == 422


def test_predio_404(client):
    t, _ = client
    r = t.get("/api/predios/nao-existe")
    assert r.status_code == 404


def test_stats_endpoint(client):
    t, _ = client
    r = t.get("/api/stats", params={"tipo": "comercial"})
    assert r.status_code == 200
    assert r.json()["total"] == 1


# --- Integração real (pula se o banco estiver fora) --------------------------

def _db_vivo():
    try:
        with db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_vivo(), reason="MariaDB local fora do ar")
def test_integracao_bbox_coerente_com_stats():
    bbox = db.parse_bbox("-38.24,-9.41,-38.21,-9.39")
    feats = db.fetch_all_buildings(bbox=bbox, tipo="comercial")
    stats = db.fetch_stats(bbox=bbox, tipo="comercial")
    assert stats["total"] == len(feats) > 0
    assert stats["by_tipo"] == {"comercial": len(feats)}
    assert sum(c["n"] for c in stats["by_bairro_tipo"]) == len(feats)


# --- Cobertura: esconder bolinhas fora da janela com polígonos ---------------

def test_build_where_em_cobertura():
    clause, params = db.build_where(em_cobertura=True)
    assert "QG/CNEFE" in params
    assert "MBRIntersects" in clause


def test_build_where_em_cobertura_combina_com_bbox():
    clause, params = db.build_where(
        bbox=(-38.24, -9.41, -38.21, -9.39), em_cobertura=True)
    assert clause.count("MBRIntersects") == 2
    assert params[-2] == "QG/CNEFE"


def test_build_where_em_cobertura_nao_some_com_fonte_nula():
    # `fonte != x` dá NULL quando fonte é NULL e a linha sumia.
    clause, _ = db.build_where(em_cobertura=True)
    assert "fonte <=> %s" in clause
    assert "fonte !=" not in clause


@pytest.mark.skipif(not _db_vivo(), reason="MariaDB local fora do ar")
def test_integracao_em_cobertura_remove_so_bolinhas_fora():
    # Cobertura municipal: tudo dentro da janela.
    total = db.fetch_stats()["total"]
    filtrado = db.fetch_stats(em_cobertura=True)["total"]
    assert total == filtrado > 20000
    feats = db.fetch_all_buildings(em_cobertura=True, limit=20000)
    assert len(feats) == 20000  # primeira página cheia: sem furo


@pytest.mark.skipif(not _db_vivo(), reason="MariaDB local fora do ar")
def test_integracao_predios_um_por_poligono():
    stats = db.fetch_stats()
    predios = db.fetch_predios(limit=db.MAX_LIMIT)
    assert len(predios) == min(stats["predios"], db.MAX_LIMIT)
    detalhe = db.fetch_predio(predios[0]["id"])
    assert len(detalhe["properties"]["enderecos"]) == predios[0]["properties"]["n"]
