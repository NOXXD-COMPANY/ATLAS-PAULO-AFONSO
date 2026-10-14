"""API do Atlas Urbano: edificações como GeoJSON para o frontend."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from . import db

app = FastAPI(title="Atlas Urbano", version="0.1.0")

# GeoJSON comprime ~8x: sem isso cada página de 5 mil ia com ~13 MB.
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
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
    em_cobertura: bool = Query(
        default=False,
        description="Esconde bolinhas fora da janela com polígonos",
    ),
    limit: int | None = Query(default=None, ge=1, le=db.MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
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
        limit=limit,
        offset=offset,
        em_cobertura=em_cobertura,
    )
    body = {
        "type": "FeatureCollection",
        "name": "buildings",
        "features": features,
    }
    return JSONResponse(content=body)


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


@app.get("/api/predios")
def list_predios(
    em_cobertura: bool = Query(default=False),
    limit: int = Query(default=db.MAX_LIMIT, ge=1, le=db.MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
):
    """Um polígono por prédio, com o ponto no centro: o que o mapa desenha."""
    features = db.fetch_predios(
        limit=limit, offset=offset, em_cobertura=em_cobertura)
    return JSONResponse(content={
        "type": "FeatureCollection",
        "name": "predios",
        "features": features,
    })


@app.get("/api/predios/{predio_id}")
def get_predio(predio_id: str):
    """Um prédio com todos os endereços ligados a ele, ou 404."""
    feature = db.fetch_predio(predio_id)
    if feature is None:
        return JSONResponse(
            content={"detail": "predio not found"}, status_code=404
        )
    return JSONResponse(content=feature)


@app.get("/api/buildings/{building_id}")
def get_building(building_id: str):
    """Uma edificação específica, ou 404."""
    feature = db.fetch_building(building_id)
    if feature is None:
        return JSONResponse(
            content={"detail": "building not found"}, status_code=404
        )
    return JSONResponse(content=feature)