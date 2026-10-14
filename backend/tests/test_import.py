"""Testes do cruzamento endereço × prédio (import_data), sem banco."""

import json

from shapely.geometry import Point, box, shape

import import_data as imp

M = 0.000009  # ~1 m em graus, perto do Equador


def _predio(id_, x, y, lado_m=10, **props):
    g = box(x, y, x + lado_m * M, y + lado_m * M)
    return {"id": id_, "geometry": g.__geo_interface__, "properties": props}


def _endereco(code, x, y, especie="1"):
    return {"geometry": {"type": "Point", "coordinates": [x, y]},
            "properties": {"COD_UNICO_ENDERECO": code, "COD_ESPECIE": especie,
                           "LOGRAD_NUM": f"Rua {code}", "DSC_LOCALIDADE": "CENTRO"}}


X, Y = -38.22, -9.40


def test_associar_dentro_tolerancia_e_longe():
    polys = imp.valid_polys([_predio("a", X, Y)])
    pts = [
        _endereco("dentro", X + 5 * M, Y + 5 * M),
        _endereco("10m", X - 10 * M, Y + 5 * M),
        _endereco("50m", X - 50 * M, Y + 5 * M),
    ]
    to_bldg, to_osm = imp.associar(polys, [], pts)
    assert to_bldg == {0: 0, 1: 0}  # 50 m fica sem prédio
    assert to_osm == {}


def test_associar_liga_sobra_ao_predio_livre_ate_30m():
    # "a" tem endereço dentro; "b" está a ~25 m da sobra e não tem nenhum.
    polys = imp.valid_polys([_predio("a", X, Y), _predio("b", X + 40 * M, Y)])
    pts = [
        _endereco("dentro-a", X + 5 * M, Y + 5 * M),
        _endereco("sobra", X + 75 * M, Y + 5 * M),  # 25 m à direita de "b"
    ]
    to_bldg, _ = imp.associar(polys, [], pts)
    assert to_bldg == {0: 0, 1: 1}


def test_associar_nao_liga_a_predio_ja_ocupado():
    # A sobra está a ~20 m de "a", mas "a" já tem endereço: continua bolinha.
    polys = imp.valid_polys([_predio("a", X, Y)])
    pts = [_endereco("dentro", X + 5 * M, Y + 5 * M),
           _endereco("sobra", X + 30 * M, Y + 5 * M)]
    to_bldg, _ = imp.associar(polys, [], pts)
    assert to_bldg == {0: 0}


def test_associar_osm_pega_o_que_overture_nao_cobre():
    polys = imp.valid_polys([_predio("a", X, Y)])
    osm = imp.valid_polys([_predio("w1", X + 200 * M, Y)])
    pts = [_endereco("no-osm", X + 205 * M, Y + 5 * M)]
    to_bldg, to_osm = imp.associar(polys, osm, pts)
    assert to_bldg == {} and to_osm == {0: 0}


def test_centro_fica_dentro_de_predio_em_L():
    l = shape({"type": "Polygon", "coordinates": [[
        [0, 0], [10, 0], [10, 1], [1, 1], [1, 10], [0, 10], [0, 0]]]})
    assert not l.contains(l.centroid)
    assert l.contains(imp.centro(l))
    quadrado = box(0, 0, 2, 2)
    assert imp.centro(quadrado).equals(Point(1, 1))


def test_tipo_dominante():
    assert imp.tipo_dominante(["residencial", "comercial", "comercial"]) == "comercial"
    assert imp.tipo_dominante(["desconhecido", "desconhecido", "servico"]) == "servico"
    assert imp.tipo_dominante(["desconhecido"]) == "desconhecido"


def test_montar_predios_e_linhas():
    predios = [_predio("a", X, Y, subtype="residential"),
               _predio("vazio", X + 500 * M, Y)]
    pts = [
        _endereco("1", X + 2 * M, Y + 2 * M, especie="6"),  # comercial
        _endereco("2", X + 8 * M, Y + 8 * M, especie="6"),
        _endereco("3", X + 5 * M, Y + 5 * M, especie="1"),  # residencial
        _endereco("4", X + 300 * M, Y),  # longe de tudo: bolinha
    ]
    rows, predio_rows = imp.montar(predios, pts, [])

    por_id = {r[0]: r for r in rows}
    assert set(por_id) == {"1", "2", "3", "4", "vazio"}
    assert {por_id[c][9] for c in "123"} == {"a"}  # predio_id
    assert por_id["4"][8] == "QG/CNEFE" and por_id["4"][9] == "4"

    p = {r[0]: r for r in predio_rows}
    assert set(p) == {"a", "vazio", "4"}
    pid, geom, ponto, area, tipo, num_pav, fonte, n = p["a"]
    assert (tipo, n) == ("comercial", 3)
    assert 90 < area < 110  # 10 m × 10 m
    assert shape(json.loads(geom)).contains(shape(json.loads(ponto)))
    assert p["vazio"][7] == 0
    assert p["4"][7] == 1


def test_montar_osm_repetindo_overture_nao_duplica():
    overture = [_predio("a", X, Y)]
    osm = [_predio("x", X + 1 * M, Y + 1 * M, osm_id="way/1"),  # em cima de "a"
           _predio("y", X + 300 * M, Y, osm_id="way/2")]  # onde o Overture não cobre
    _, predio_rows = imp.montar(overture, [], osm)
    assert sorted(r[0] for r in predio_rows) == ["a", "osm-way-2"]


def test_montar_ids_duplicados_ganham_sufixo():
    pts = [_endereco("dup", X, Y), _endereco("dup", X + 900 * M, Y)]
    rows, predio_rows = imp.montar([], pts, [])
    assert sorted(r[0] for r in rows) == ["dup#1", "dup#2"]
    assert sorted(r[0] for r in predio_rows) == ["dup#1", "dup#2"]


class _CursorFalso:
    def __init__(self, existentes):
        self.existentes, self.sql, self._ultimo = existentes, [], None

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self._ultimo = params[0] if params else None

    def fetchone(self):
        return (self._ultimo,) if self._ultimo in self.existentes else None


def test_publicar_troca_tudo_num_rename_so():
    cur = _CursorFalso(existentes={"buildings"})  # 1ª carga com `predios`
    imp.publicar(cur)
    renames = [s for s in cur.sql if s.startswith("RENAME")]
    assert renames == ["RENAME TABLE buildings TO buildings_old, "
                       "buildings_new TO buildings, predios_new TO predios"]
    assert cur.sql[-1] == "DROP TABLE buildings_old"
