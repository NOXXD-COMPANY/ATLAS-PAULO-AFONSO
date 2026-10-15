"""Testes essenciais (P6): só pontos críticos, sem cobertura completa.

Roda com: ./.venv/bin/python -m pytest backend/tests -q
(dependências de dev: pytest, httpx)
"""

import pytest

from backend import db
from backend.schemas import (
    FeatureFull,
    FeatureLight,
    StatsResponse,
)


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
    assert clause == "WHERE (bairro IN (%s))"
    assert params == ["CENTRO"]


# --- P3: conversão para GeoJSON ---------------------------------------------

def _row(full=True):
    base = {"ST_AsGeoJSON(geom)": '{"type":"Point","coordinates":[-38.2,-9.4]}'}
    if full:
        base.update({
            "id": "x1", "area_m2": 112.5, "tipo": None, "endereco": "Rua A",
            "bairro": "CENTRO", "estabelecimento": None,
            "num_pavimentos": 2, "fonte": "QG/CNEFE",
        })
    else:
        base.update({"id": "x1", "tipo": "comercial", "fonte": "OSM",
                     "num_pavimentos": None})
    return base


def test_row_to_feature_normaliza_tipo():
    f = db.row_to_feature(_row())
    assert f["type"] == "Feature"
    assert f["properties"]["tipo"] == "desconhecido"  # None → fallback
    FeatureFull.model_validate(f)  # contrato válido


def test_row_to_light_feature_minimo():
    f = db.row_to_light_feature(_row(full=False))
    assert set(f["properties"]) == {"id", "geometry_key", "tipo", "fonte", "num_pavimentos"}
    assert "endereco" not in f["properties"]
    FeatureLight.model_validate(f)


def test_stats_schema():
    s = StatsResponse.model_validate({
        "total": 10, "by_tipo": {"residencial": 10},
        "by_bairro": {"CENTRO": 10},
        "area_total_m2": 1000.0, "area_media_m2": 100.0,
    })
    assert s.total == 10


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


def test_stats_endpoint(client):
    t, _ = client
    r = t.get("/api/stats", params={"tipo": "comercial"})
    assert r.status_code == 200
    assert r.json()["total"] == 1


@pytest.mark.parametrize("z", [2, 12, 17])
def test_tile_preserva_eixo_y_para_coordenadas_mvt(monkeypatch, z):
    """Em MVT, latitude sul deve aumentar Y a partir do topo do tile."""
    import math
    from shapely.geometry import Polygon
    from backend import main
    import mapbox_vector_tile

    scale = 1 << z
    x, y = scale // 2, scale // 2
    longitude = (x + 0.5) / scale * 360 - 180
    local_y = 1024
    latitude = math.degrees(math.atan(math.sinh(
        math.pi * (1 - 2 * (y + local_y / 4096) / scale))))
    delta = 360 / scale * 0.01

    monkeypatch.setattr(main.db, "fetch_building_tile", lambda bounds: [{
        "type": "Feature",
        "id": "tile-test",
        "geometry": Polygon([
            (longitude - delta, latitude - delta),
            (longitude + delta, latitude - delta),
            (longitude + delta, latitude + delta),
            (longitude - delta, latitude + delta),
            (longitude - delta, latitude - delta),
        ]),
        "properties": {"id": "tile-test", "geometry_key": "tile-test"},
    }])

    body = main._building_tile_bytes(z, x, y)
    # O decoder padrão também inverte Y. Leia os valores MVT crus, como o
    # navegador, para não mascarar uma inversão incorreta do encoder.
    decoded = mapbox_vector_tile.decode(body, default_options={"y_coord_down": True})
    ring = decoded["buildings"]["features"][0]["geometry"]["coordinates"][0]

    extent = decoded["buildings"]["extent"]
    assert sum(tile_y for _, tile_y in ring) / len(ring) < extent / 2


def test_tile_recorta_predio_que_cruza_blocos_sem_perder_partes(monkeypatch):
    import math
    import mapbox_vector_tile
    from shapely.geometry import Polygon, shape
    from backend import main

    z, x, y = 17, 51619, 68974
    scale = 1 << z
    border = (x + 1) / scale * 360 - 180
    latitude = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / scale))))
    delta = 360 / scale * 0.1
    geometry = Polygon([(border - delta, latitude - delta), (border + delta, latitude - delta),
                        (border + delta, latitude + delta), (border - delta, latitude + delta)])
    monkeypatch.setattr(main.db, "fetch_building_tile", lambda bounds: [{
        "geometry": geometry, "properties": {"id": "boundary", "geometry_key": "same-building"},
    }])
    for tile_x in [x, x + 1]:
        tile = mapbox_vector_tile.decode(main._building_tile_bytes(z, tile_x, y),
                                        default_options={"y_coord_down": True})["buildings"]
        assert len(tile["features"]) == 1
        feature = tile["features"][0]
        assert feature["properties"]["geometry_key"] == "same-building"
        bounds = shape(feature["geometry"]).bounds
        assert -8 <= bounds[0] < bounds[2] <= tile["extent"] + 8


def test_tile_cache_reutiliza_blocos_e_expira(monkeypatch):
    from backend import main
    from backend.tile_cache import TileCache
    from fastapi.testclient import TestClient

    calls = []
    now = [301]
    monkeypatch.setattr(main, "tile_cache", TileCache(clock=lambda: now[0]))
    monkeypatch.setattr(main, "_building_tile_bytes", lambda *args: calls.append(args) or b'tile')
    with TestClient(main.app) as client:
        first = client.get('/api/tiles/17/51619/68974.pbf')
        second = client.get('/api/tiles/17/51619/68974.pbf')
        assert first.status_code == second.status_code == 200
        assert first.content == second.content
        assert len(calls) == 1
        now[0] = 602
        assert client.get('/api/tiles/17/51619/68974.pbf').status_code == 200
        assert len(calls) == 2


def test_tile_cache_limita_bytes_e_quantidade():
    from backend.tile_cache import TileCache

    cache = TileCache(max_bytes=10, max_items=2)
    cache.put('a', b'1234')
    cache.put('b', b'5678')
    assert cache.get('a') == b'1234'
    cache.put('c', b'9012')
    assert cache.get('b') is None
    assert cache.size == 8
    cache.put('large', b'12345678901')
    assert cache.size == 8
    assert cache.get('large') is None


def test_tile_cancelado_para_a_geracao_no_servidor(monkeypatch):
    import asyncio
    from threading import Event
    from concurrent.futures import CancelledError
    from backend import main
    from backend.tile_cache import TileCache

    started, stopped = Event(), Event()
    def slow_tile(z, x, y, cancelled):
        started.set()
        try:
            if cancelled.wait(timeout=2):
                raise CancelledError()
            pytest.fail('Geração continuou mesmo após cancelar o pedido')
        finally:
            stopped.set()
    class Disconnected:
        async def is_disconnected(self):
            return started.is_set()

    monkeypatch.setattr(main, 'tile_cache', TileCache())
    monkeypatch.setattr(main, '_building_tile_bytes', slow_tile)
    response = asyncio.run(main.building_tile(17, 51619, 68974, Disconnected()))
    assert response.status_code == 499
    assert stopped.wait(timeout=1)
    assert main.tile_cache.size == 0


def test_encoder_interrompe_antes_de_consultar_banco(monkeypatch):
    from threading import Event
    from concurrent.futures import CancelledError
    from backend import main

    cancelled = Event()
    cancelled.set()
    monkeypatch.setattr(main.db, 'fetch_building_tile', lambda *args, **kwargs: pytest.fail('Consultou banco após cancelamento'))
    with pytest.raises(CancelledError):
        main._building_tile_bytes(17, 51619, 68974, cancelled)


def test_blocos_pendentes_nao_bloqueiam_api_e_geram_so_dois_por_vez(monkeypatch):
    import asyncio
    from threading import Lock
    from concurrent.futures import CancelledError
    import httpx
    from backend import main
    from backend.tile_cache import TileCache

    active = [0]
    maximum = [0]
    lock = Lock()
    def slow_tile(z, x, y, cancelled):
        with lock:
            active[0] += 1
            maximum[0] = max(maximum[0], active[0])
        try:
            cancelled.wait(timeout=2)
            raise CancelledError()
        finally:
            with lock:
                active[0] -= 1

    monkeypatch.setattr(main, 'tile_cache', TileCache())
    monkeypatch.setattr(main, '_building_tile_bytes', slow_tile)
    async def exercise():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            requests = [asyncio.create_task(client.get(f'/api/tiles/17/{51619 + i}/68974.pbf'))
                        for i in range(6)]
            try:
                for _ in range(100):
                    if active[0] == 2:
                        break
                    await asyncio.sleep(0.01)
                response = await asyncio.wait_for(client.get('/'), timeout=0.5)
                assert response.status_code == 200
                assert maximum[0] == 2
            finally:
                for request in requests:
                    request.cancel()
                await asyncio.gather(*requests, return_exceptions=True)
    asyncio.run(exercise())


def test_tile_consulta_todos_poligonos_do_bloco_sem_filtro_de_cobertura(monkeypatch):
    from unittest.mock import MagicMock

    first = _row(full=False)
    duplicate = {**first, "id": "duplicate"}
    other = {**first, "id": "other", "ST_AsGeoJSON(geom)":
             '{"type":"Polygon","coordinates":[[[-38.2,-9.4],[-38.1,-9.4],[-38.1,-9.3],[-38.2,-9.4]]]}'}
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [first, duplicate, other]
    monkeypatch.setattr(db, "connect", lambda: connection)

    features = db.fetch_building_tile((-38.3, -9.5, -38.0, -9.2))
    sql, params = cursor.execute.call_args.args
    assert "MBRIntersects" in sql
    assert "LIMIT" not in sql
    assert len(params) == 1
    assert len(features) == 2


# --- Integração real (pula se o banco estiver fora) --------------------------

def _db_vivo():
    try:
        with db.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_vivo(), reason="MariaDB local fora do ar")
@pytest.mark.parametrize("z,x,y", [(17, 51619, 68974), (13, 3226, 4310)])
def test_integracao_tile_contem_todos_footprints_visiveis(z, x, y):
    import math
    import mapbox_vector_tile
    from shapely.geometry import box
    from backend import main

    scale = 1 << z
    def latitude(tile_y):
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * tile_y / scale))))
    bounds = (x / scale * 360 - 180, latitude(y + 1),
              (x + 1) / scale * 360 - 180, latitude(y))
    window = box(*bounds)
    # A consulta MBR pode incluir polígonos cuja caixa toca o bloco, mas cuja
    # área fica inteiramente fora. Todos os que realmente entram devem sair.
    expected = {
        feature["properties"]["geometry_key"]
        for feature in db.fetch_building_tile(bounds)
        if feature["geometry"].intersection(window).area > 0
    }
    tile = mapbox_vector_tile.decode(main._building_tile_bytes(z, x, y),
                                    default_options={"y_coord_down": True})["buildings"]
    actual = {feature["properties"]["geometry_key"] for feature in tile["features"]}
    assert expected
    assert expected <= actual, f"Footprints ausentes: {sorted(expected - actual)}"


@pytest.mark.skipif(not _db_vivo(), reason="MariaDB local fora do ar")
def test_integracao_bbox_coerente_com_stats():
    bbox = db.parse_bbox("-38.24,-9.41,-38.21,-9.39")
    feats = db.fetch_all_buildings(bbox=bbox, tipo="comercial", light=True)
    stats = db.fetch_stats(bbox=bbox, tipo="comercial")
    assert stats["total"] == len(feats) > 0
    assert stats["by_tipo"] == {"comercial": len(feats)}
    for f in feats:
        FeatureLight.model_validate(f)


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


@pytest.mark.skipif(not _db_vivo(), reason="MariaDB local fora do ar")
def test_integracao_em_cobertura_remove_so_bolinhas_fora():
    # Cobertura municipal: 87951 linhas, tudo dentro da janela.
    total = db.fetch_stats()["total"]
    filtrado = db.fetch_stats(em_cobertura=True)["total"]
    assert (total, filtrado) == (87951, 87951)
    feats = db.fetch_all_buildings(em_cobertura=True, limit=20000)
    assert len(feats) == 20000  # primeira página cheia: sem furo
