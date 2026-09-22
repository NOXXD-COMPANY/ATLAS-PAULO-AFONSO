# Atlas Urbano — MVP

Visualizador de **edificações reais** sobre um mapa interativo. O fluxo validado:

```
dados reais (Overture + QG/CNEFE)
        ↓
    MySQL (tabela espacial `buildings`)
        ↓
    FastAPI (GET /api/buildings, /api/buildings/{id})
        ↓
    React + MapLibre + deck.gl
        ↓
          MAPA
```

## Dados usados

| Fonte                            | O que fornece                                   |
| -------------------------------- | ----------------------------------------------- |
| `overture-...-building-*.geojson`| Polígono real de cada edificação (8.382)        |
| `qg_810_endereco_*.json`         | Endereços/estabelecimentos (61.965 pontos QG)   |

A tabela `buildings` tem uma linha por endereço QG (61.965) mais os
prédios Overture sem nenhum endereço (3.316), totalizando 65.281
edificações. Endereço dentro de um prédio usa o polígono dele (relação
espacial com ~15 m de tolerância na borda); endereço sem prédio vira um
círculo de ~5 m ao redor do ponto. O QG cobre Paulo Afonso inteira e o
Overture só a janela do mapa, por isso só ~26% dos endereços têm polígono.
O tipo de uso vem do **código de espécie** do QG (`1`=residencial,
`2`=hospedagem, `3`=agropecuário, `4`=institucional, `5`=serviço,
`6`=comercial, `8`=religioso); `7` (em construção) e sem informação →
`desconhecido`. Na legenda há um checkbox para mostrar ou ocultar os
endereços sem prédio.

## Como rodar

Pré-requisitos: Python 3, Node.js, e o `mariadb`/`mariadbd` do sistema já
instalados (não precisa rodar o MariaDB como serviço — o script sobe uma
instância local).

```bash
# 1) Ambiente Python (uma vez)
python3 -m venv .venv
./.venv/bin/pip install -r backend/requirements.txt

# 2) Instalar o app (uma vez)
cd frontend && npm install && cd ..

# 3) Tudo de uma vez
bash scripts/run.sh
```

Ou passo a passo:

```bash
bash scripts/db.sh start      # sobe o MariaDB local (:3306, db atlas_urbano)
./.venv/bin/python import_data.py   # importa e relaciona os dados
./.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
cd frontend && npm run dev -- --port 5173 &
```

Abra **http://127.0.0.1:5173/**.

## Estrutura

```
backend/            API FastAPI (nunca acessa o MySQL pelo frontend)
  config.py         conexão/credenciais do banco
  db.py             consultas → GeoJSON
  main.py           rotas /api/buildings e /api/buildings/{id}
  requirements.txt  dependências Python do backend
frontend/           React + Vite + TS + MapLibre + deck.gl
  src/App.tsx       mapa, camada de prédios, clique, painel, legenda
  src/constants.ts  cores por tipo de uso
scripts/
  db.sh             sobe/para o MariaDB local
  run.sh            sobe tudo
  mysql-local.cnf   tmpdir do MariaDB (sem /var/tmp no ambiente)
import_data.py      Overture + QG → relação espacial → tabela `buildings`
data/raw/           arquivos fornecidos (overture/ e qg/)
```

## Notas / decisões

- **3D**: habilitado apenas de forma trivial: prédios com `num_pavimentos`
  (presente em 33 edificações do Overture) recebem extrusão `pavimentos × 3 m`.
  O restante permanece 2D. A base (OpenFreeMap) também desenha os prédios
  do OSM em 3D. Incline a câmera (botão direito arrastar) para ver.
- **Ponto de extensão**: a carga estática (script) e o endpoint
  `GET /api/buildings` são os lugares onde entra uma futura fonte real
  (importação IBGE/prefeitura, filtros `?bairro=X`, paginação).