"""Visão afastada do município: uma grade com a contagem de prédios.

Abaixo do zoom 14 um prédio ocupa ~1 px; mandar os footprints nessa escala
só repete a cidade inteira em cada tile. A grade é leve, vem uma vez e
mostra onde há prédios e qual uso predomina.
"""

import math
from collections import Counter, defaultdict

FONTE_PONTO = "QG/CNEFE"
# Níveis de detalhe, do mais grosso ao mais fino (~175 e 88 m), um por nível
# de zoom. Mais perto que isso cada prédio já aparece como ponto, no tamanho
# real (frontend/src/mapTiles.ts, OVERVIEW_LEVELS).
LEVEL_CELL_DEG = (0.0016, 0.0008)


def _dominant(counts, prefixes):
    """Tipo mais frequente; `desconhecido` só vence se for o único."""
    by_tipo = Counter()
    for key, n in counts.items():
        prefix, _, tipo = key.partition("_")
        if prefix in prefixes:
            by_tipo[tipo] += n
    known = [(n, tipo) for tipo, n in by_tipo.items() if tipo != "desconhecido"]
    if known:
        return max(known)[1]
    return "desconhecido" if by_tipo else None


def build_overview(rows, cell_deg=LEVEL_CELL_DEG[0]):
    """rows: {x, y, tipo, fonte} por footprint → (FeatureCollection, bounds).

    Cada célula traz `b_<tipo>` (prédios) e `p_<tipo>` (endereços sem
    prédio) para o mapa somar a legenda com o mesmo filtro dos footprints.
    """
    cells = defaultdict(Counter)
    for row in rows:
        kind = "p" if row["fonte"] == FONTE_PONTO else "b"
        key = (math.floor(row["x"] / cell_deg), math.floor(row["y"] / cell_deg))
        cells[key][f"{kind}_{row['tipo'] or 'desconhecido'}"] += 1

    features = []
    for (cx, cy), counts in sorted(cells.items()):
        west, south = round(cx * cell_deg, 6), round(cy * cell_deg, 6)
        east, north = round((cx + 1) * cell_deg, 6), round((cy + 1) * cell_deg, 6)
        cell_id = f"{cx}:{cy}"
        features.append({
            "type": "Feature",
            "id": cell_id,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[west, south], [east, south], [east, north],
                                 [west, north], [west, south]]],
            },
            "properties": {
                "id": cell_id,
                "n_b": sum(n for k, n in counts.items() if k.startswith("b_")),
                "n_p": sum(n for k, n in counts.items() if k.startswith("p_")),
                "tipo_b": _dominant(counts, {"b"}) or "desconhecido",
                "tipo": _dominant(counts, {"b", "p"}),
                **counts,
            },
        })

    bounds = None
    if cells:
        xs = [cx for cx, _ in cells]
        ys = [cy for _, cy in cells]
        bounds = [round(min(xs) * cell_deg, 6), round(min(ys) * cell_deg, 6),
                  round((max(xs) + 1) * cell_deg, 6), round((max(ys) + 1) * cell_deg, 6)]
    return {"type": "FeatureCollection", "features": features}, bounds
