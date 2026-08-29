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

### 4. LOGS ESTRUTURADOS


#### BACKEND 

Logs são escritos em JSON (uma entrada por linha) em `logs/pipeline_YYYY-MM-DD.log` e em formato legível no console.

```bash
# LOGS MAIS SIMPLES
python backend/processar_dados.py

# LOGS MAIS DETALHADOS PARA DEBUG
python backend/processar_dados.py --debug

# DIRETORIO DA SUA ESCOLHA
python backend/processar_dados.py --log-dir ./meus_logs
```

#### FRONTEND CONSOLE DO NAVEGADOR

Logs são armazenados em `localStorage` (últimas 500 entradas) e impressos no console do navegador com timestamps e IDs de sessão.

```js
// NO CONSOLE DO NAVEGADO - F12 
__AtlasLogs.export()     // RETORNA O JSON NO CONSOLE [TUDO]
__AtlasLogs.download()   // BAIXA OS LOGS EM JSON
__AtlasLogs.clear()      // LIMPA O CONSOLE
```

LOG PARA DEBUG, VA NA URL `?logLevel=debug` :
```
http://127.0.0.1:8080/frontend/?logLevel=debug
```
