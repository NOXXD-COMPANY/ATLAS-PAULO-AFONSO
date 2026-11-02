from importacao.cli import main

from importacao.espacial import match_points, polygon_of
from importacao.classificacao import best_type, classify 
from importacao.fontes import (
    boundary_shape, load_buildings, load_osm_buildings, load_qg_points)
from importacao.predios import fonte_principal, montar_predios 
from importacao.producao import colunas_gravaveis, promover 
from importacao.stage import gravar_stage 

if __name__ == "__main__":
    main()
