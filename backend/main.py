"""API do Atlas Urbano — MVP.

Retorna as edificações como GeoJSON para o frontend (React/deck.gl).

PONTO DE EXTENSÃO FUTURA:
  - Quando houver autenticação, adicionar dependências de auth por rota.
  - Se a carga ficar pesada, adicionar paginação / filtros (bairro, tipo)
    aqui mesmo, sem mudar o frontend: GET /api/buildings?bairro=X&tipo=Y.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db

app = FastAPI(title="Atlas Urbano", version="0.1.0")

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
def list_buildings():
    """Todas as edificações em GeoJSON (FeatureCollection)."""
    features = db.fetch_all_buildings()
    body = {
        "type": "FeatureCollection",
        "name": "buildings",
        "features": features,
    }
    return JSONResponse(content=body)


@app.get("/api/buildings/{building_id}")
def get_building(building_id: str):
    """Uma edificação específica, ou 404."""
    feature = db.fetch_building(building_id)
    if feature is None:
        return JSONResponse(
            content={"detail": "building not found"}, status_code=404
        )
    return JSONResponse(content=feature)