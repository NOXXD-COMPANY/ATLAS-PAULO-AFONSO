"""API do Atlas Urbano: detalhes GeoJSON e mapa em tiles vetoriais."""

import asyncio
import math
from concurrent.futures import CancelledError, ThreadPoolExecutor
from threading import Event

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from shapely.ops import transform as transform_geometry
from shapely.geometry import box
import mapbox_vector_tile

from . import db
from .tile_cache import TileCache

app = FastAPI(title="Atlas Urbano", version="0.1.0")
tile_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="map-tiles")
tile_cache = TileCache()

# Mantém compactas as respostas JSON e os tiles vetoriais maiores.
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    return {"status": "ok", "service": "atlas-urbano-api"}


@app.get("/api/buildings")
def list_buildings(
    bbox: str | None = Query(
        default=None,
        description="Área visível: minLng,minLat,maxLng,maxLat",
    ),
    bairro: list[str] | None = Query(default=None),
    tipo: str | None = None,
    fonte: str | None = None,
    light: bool = Query(
        default=False,
        description="Só campos de renderização (tipo, fonte, num_pavimentos)",
    ),
    em_cobertura: bool = Query(
        default=False,
        description="Esconde bolinhas fora da janela com polígonos",
    ),
    limit: int | None = Query(default=None, ge=1, le=db.MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    after_id: str | None = Query(default=None),
):
    """Edificações em GeoJSON, com filtros e paginação opcionais.

    Sem parâmetros mantém o comportamento antigo (tudo de uma vez).
    """
    try:
        parsed_bbox = db.parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=422, detail="bbox inválido")
    features = db.fetch_all_buildings(
        bbox=parsed_bbox,
        bairros=bairro,
        tipo=tipo,
        fonte=fonte,
        light=light,
        limit=limit,
        offset=offset,
        after_id=after_id,
        em_cobertura=em_cobertura,
    )
    body = {
        "type": "FeatureCollection",
        "name": "buildings",
        "features": features,
    }
    return JSONResponse(content=body)


@app.get("/api/tiles/{z}/{x}/{y}.pbf")
async def building_tile(z: int, x: int, y: int, request: Request):
    """Tile vetorial binário: só transfere geometrias da área pedida."""
    if z < 0 or z > 20:
        raise HTTPException(status_code=404, detail="tile fora do zoom suportado")
    scale = 1 << z
    if x < 0 or y < 0 or x >= scale or y >= scale:
        raise HTTPException(status_code=404, detail="tile fora do mapa")
    key = (z, x, y)
    body = tile_cache.get(key)
    if body is None:
        cancelled = Event()
        future = tile_executor.submit(_building_tile_bytes, z, x, y, cancelled)
        try:
            # O cancelamento HTTP precisa chegar à consulta e ao encoder.
            # Só cancelar o fetch deixava dezenas de gerações consumindo RAM/CPU.
            while not future.done():
                if await request.is_disconnected():
                    cancelled.set()
                    future.cancel()
                    return Response(status_code=499)
                await asyncio.sleep(0.05)
            body = future.result()
        except asyncio.CancelledError:
            cancelled.set()
            future.cancel()
            raise
        except CancelledError:
            return Response(status_code=499)
        tile_cache.put(key, body)
    return Response(
        content=body,
        media_type="application/vnd.mapbox-vector-tile",
        headers={"Cache-Control": "public, max-age=300"},
    )


def _building_tile_bytes(z: int, x: int, y: int, cancelled: Event | None = None):
    """Gera um bloco, interrompendo antes de cada geometria se saiu da visão."""
    def check_cancelled():
        if cancelled is not None and cancelled.is_set():
            raise CancelledError()

    check_cancelled()
    scale = 1 << z

    def tile_lat(tile_y):
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * tile_y / scale))))

    west = x / scale * 360 - 180
    east = (x + 1) / scale * 360 - 180
    north = tile_lat(y)
    south = tile_lat(y + 1)
    geographic_bounds = (west, south, east, north)
    radius = 6378137.0
    projected_bounds = (
        radius * math.radians(west),
        radius * math.asinh(math.tan(math.radians(south))),
        radius * math.radians(east),
        radius * math.asinh(math.tan(math.radians(north))),
    )

    # Mantém precisão submétrica também ao afastar a câmera. Uma resolução
    # muito baixa faz pequenos prédios desaparecerem durante a quantização.
    extent = min(1048576, 8192 << max(0, 14 - z))
    tolerance = (projected_bounds[2] - projected_bounds[0]) / extent * 0.75
    clip_bounds = box(*projected_bounds).buffer(tolerance * 8, cap_style=3, join_style=2)

    def features():
        rows = (db.fetch_building_tile(geographic_bounds, cancelled=cancelled)
                if cancelled is not None else db.fetch_building_tile(geographic_bounds))
        for feature in rows:
            check_cancelled()
            geometry = transform_geometry(
                lambda lon, lat, z=None: (
                    radius * math.radians(lon),
                    radius * math.asinh(math.tan(math.radians(max(-85.05112878, min(85.05112878, lat))))),
                ),
                feature["geometry"],
            )
            if not geometry.is_valid:
                geometry = geometry.buffer(0)
            geometry = geometry.intersection(clip_bounds)
            if geometry.is_empty or geometry.geom_type not in ("Polygon", "MultiPolygon", "Point", "MultiPoint"):
                continue
            yield {
                "geometry": geometry.simplify(tolerance, preserve_topology=True),
                "properties": feature["properties"],
            }
    tile = mapbox_vector_tile.encode(
        [{"name": "buildings", "features": features()}],
        # A projeção acima tem Y para cima. O encoder precisa invertê-lo uma
        # vez para as coordenadas MVT (origem no topo, Y para baixo).
        default_options={
            "quantize_bounds": projected_bounds,
            "extents": extent,
            "y_coord_down": False,
        },
    )
    return tile


@app.get("/api/stats")
def get_stats(
    bbox: str | None = Query(default=None),
    bairro: list[str] | None = Query(default=None),
    tipo: str | None = None,
    fonte: str | None = None,
    em_cobertura: bool = Query(default=False),
):
    """Agregados (total, por tipo/bairro, áreas) com os mesmos filtros."""
    try:
        parsed_bbox = db.parse_bbox(bbox)
    except ValueError:
        raise HTTPException(status_code=422, detail="bbox inválido")
    return JSONResponse(content=db.fetch_stats(
        bbox=parsed_bbox, bairros=bairro, tipo=tipo, fonte=fonte,
        em_cobertura=em_cobertura))


@app.get("/api/buildings/{building_id}")
def get_building(building_id: str):
    """Uma edificação específica, ou 404."""
    feature = db.fetch_building(building_id)
    if feature is None:
        return JSONResponse(
            content={"detail": "building not found"}, status_code=404
        )
    return JSONResponse(content=feature)
