# Atlas Urbano de Paulo Afonso — Projeto de Extensão 2026.2

Inventário aberto de edificações e endereços de Paulo Afonso/BA com estatísticas territoriais e mapa interativo, combinando dados do Censo 2022 (CNEFE / IBGE) com bases globais de polígonos de edificações (Overture Maps / Google Open Buildings).


## NECESSÁRIO

Python 3.9 ou superior.

Instale as dependências:

pip install -r requirements.txt

Dependências utilizadas:
* `shapely`: Operações geométricas e indexação espacial R-tree (STRtree).
* `pyproj`: Projeção cartográfica SIRGAS 2000 / UTM Zona 24S (EPSG:31984) para cálculo de área em m².


### 1. PROCESSAR DADOS

python backend/processar_dados.py

Lê os arquivos de `data/raw/`, executa a junção espacial e gera as saídas em `data/processed/`.

### 2. SERVIDOR LOCAL 

python -m http.server 8080

### 3. URL DO NAVEGADOR

* Raiz do projeto: http://127.0.0.1:8080/
* Aplicação web (mapa): http://127.0.0.1:8080/frontend/
