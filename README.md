# Atlas Urbano de Paulo Afonso — MVP

Visualizador de **edificações reais** sobre um mapa interativo, aplicado a Paulo Afonso/BA. O sistema cruza fontes abertas (polígonos de prédios do Overture Maps, com o OpenStreetMap como fallback, e endereços do CNEFE/IBGE), grava o resultado num banco espacial e o expõe por uma API REST em GeoJSON, consumida por um frontend com mapa 3D, legenda por tipo de uso, painel de detalhes e relatório exportável.

> **Retrato estatístico, não cadastro oficial.** Pegada de edificação ≠ área construída, e *footprint* ≠ terreno. Os números refletem as fontes usadas (CNEFE 2022, Overture e OSM) e herdam as limitações delas (ver [Limitações conhecidas](#limitações-conhecidas)).

## Equipe

Projeto da turma de Sistemas de Informação, Paulo Afonso – BA.

| Função | Nome |
| --- | --- |
| Líder da equipe | Caio Lúcio |
| Membro | Arthur Henrique |
| Membro | Elliton Luís |
| Membro | Rafael Santos |
| Membro | Luís Gustavo |
| Membro | João Almeida |

Repositório: <https://github.com/NOXXD-COMPANY/ATLAS-PAULO-AFONSO>

## Sumário

1. [Problema e objetivo](#problema-e-objetivo)
2. [Fluxo do sistema](#fluxo-do-sistema)
3. [Dados usados](#dados-usados)
4. [Como rodar](#como-rodar)
5. [Arquitetura](#arquitetura)
6. [API](#api)
7. [Modelo de dados](#modelo-de-dados)
8. [Testes](#testes)
9. [Requisitos e estado de implementação](#requisitos-e-estado-de-implementação)
10. [Casos de uso](#casos-de-uso)
11. [Decisões de engenharia](#decisões-de-engenharia)
12. [Limitações conhecidas](#limitações-conhecidas)
13. [Roadmap](#roadmap)
14. [Estrutura do repositório](#estrutura-do-repositório)

---

## Problema e objetivo

Nenhuma fonte aberta responde sozinha à pergunta *"o que existe em cada prédio da cidade e onde ele está?"*:

- o **Overture Maps** (e, como complemento, o **OpenStreetMap**) fornece a **forma** (polígono) de cada edificação, com pouca informação de uso;
- o **CNEFE (IBGE)** fornece **endereço e espécie do estabelecimento** (residencial, comercial, religioso etc.), mas apenas como pontos.

O projeto integra as fontes: cada ponto de endereço é associado, por relação espacial, à edificação que o contém. O polígono vem do Overture (ou do OSM, onde o Overture não tem) e o tipo de uso vem do IBGE. O resultado serve para consulta por usuários não técnicos e como base para estatísticas por recorte territorial e, futuramente, para priorizar conferência de campo.

## Fluxo do sistema

```
dados abertos: Overture + OSM (polígonos) · QG/CNEFE (endereços)
        ↓
    ETL em Python (import_data.py)
        ↓
    MariaDB/MySQL (tabela espacial `buildings`)
        ↓
    FastAPI (/api/buildings, /api/buildings/{id}, /api/stats)
        ↓
    React + MapLibre + deck.gl
        ↓
          MAPA
```

## Dados usados

| Fonte | O que fornece | Volume |
| --- | --- | --- |
| `overture-...-building-*.geojson` (janela) + `...-building-municipio.geojson` (município inteiro, mesma release) | Polígono real de cada edificação | 52.809 prédios no município (8.382 na janela original) |
| `qg_810_endereco_*.json` (CNEFE/IBGE, município 2924009) | Endereços e estabelecimentos | 61.965 pontos |
| `osm_buildings_paulo_afonso.geojson` (2ª fonte, via API Overpass/OSM, aberta e sem login) | Polígonos onde o Overture não cobre | 400 prédios (fallback; nenhum endereço novo foi adotado, pois o Overture municipal já cobria) |

A tabela `buildings` tem uma linha por endereço QG (61.965) mais os prédios sem nenhum endereço, totalizando **87.951 registros**. 58.178 endereços (93,9%) caíram em polígono; restam 3.787 círculos ("bolinhas") de endereços sem prédio.

**Fluxo de carga com as duas fontes de polígonos:**

1. Os arquivos do Overture são unidos (sem duplicar IDs) e recortados no contorno do município (`municipio_boundary.geojson`).
2. Cada endereço é associado a um polígono do Overture.
3. Os endereços que sobraram tentam um polígono do OSM (se o arquivo existir; sem ele, o fallback é só desligado).
4. O que ainda sobrar vira círculo de ~5 m.

**Regras da junção espacial endereço × edificação** (a mesma para as duas fontes):

1. Se o ponto está **dentro** de um polígono, usa esse polígono.
2. Se não, procura polígonos a até **~15 m** (tolerância para porta na fachada ou erro de GPS).
3. Havendo mais de um candidato, escolhe o **mais próximo**.
4. Endereço sem prédio vira um **círculo de ~5 m** ao redor do ponto.

**Tipo de uso**, em ordem de prioridade:

1. código de espécie do QG: `1`=residencial, `2`=hospedagem, `3`=agropecuário, `4`=institucional, `5`=serviço, `6`=comercial, `8`=religioso; `7` (em construção) vira `desconhecido`;
2. subtipo do Overture (ex.: `residential`, `commercial`, `religious`);
3. classe do Overture, ou a tag `building` do OSM tratada como classe (ex.: `house`, `retail`, `church`);
4. `desconhecido`.

IDs de endereço duplicados no CNEFE recebem sufixo `#n`, e polígonos do OSM sem endereço entram com ID `osm-<id>`.

### Dados brutos (não versionados)

A pasta `data/raw/` está no `.gitignore`, então **quem clona o repositório precisa obter os arquivos**:

| Arquivo | Caminho | Como obter |
| --- | --- | --- |
| Overture (janela e município) | `data/raw/overture/` | A documentar (origem e parâmetros do download) |
| CNEFE/QG | `data/raw/qg/qg_810_endereco_Munic2924009.json` | A documentar (download do IBGE) |
| Contorno do município | `data/raw/municipio_boundary.geojson` | A documentar (origem) |
| OSM (opcional) | `data/raw/osm/osm_buildings_paulo_afonso.geojson` | `scripts/fetch_osm_buildings.py` |

## Como rodar

Pré-requisitos: **Python 3.10 ou superior** (a API usa a sintaxe `str | None`), Node.js, e o `mariadb`/`mariadbd` do sistema já instalados (não precisa rodar o MariaDB como serviço, pois o script sobe uma instância local). Os arquivos de dados brutos devem estar em `data/raw/` (ver acima).

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
# (opcional, demora vários minutos) baixa a 2ª fonte de polígonos do OSM
./.venv/bin/python scripts/fetch_osm_buildings.py

bash scripts/db.sh start            # sobe o MariaDB local (:3306, db atlas_urbano)
./.venv/bin/python import_data.py   # importa e relaciona os dados
./.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
cd frontend && npm run dev -- --port 5173 &
```

Abra **http://127.0.0.1:5173/**. Para parar o banco: `bash scripts/db.sh stop`.

**Portas e serviços**

| Serviço | Endereço |
| --- | --- |
| MariaDB local | `127.0.0.1:3306` (banco `atlas_urbano`) |
| Backend FastAPI | `http://127.0.0.1:8000` (docs interativas em `/docs`) |
| Frontend Vite | `http://127.0.0.1:5173` |

**Logs:** `/tmp/atlas-uvicorn.log` (backend), `/tmp/atlas-vite.log` (frontend) e `.mysql-data/mysql.err` (banco).

**Configuração**

- Banco (backend): `backend/config.py`.
- Banco (carga): constantes no topo de `import_data.py`. **Atenção:** hoje elas apontam para uma instância diferente da que o `db.sh` sobe (porta e usuário distintos), e a credencial está escrita no arquivo. Alinhar com `config.py` e mover para variáveis de ambiente (ver [Limitações conhecidas](#limitações-conhecidas)).
- Frontend: a variável `VITE_API_URL` define o endereço da API (padrão `http://127.0.0.1:8000`).
- CORS: o backend aceita apenas `localhost:5173` e `127.0.0.1:5173`.

## Arquitetura

Arquitetura em **camadas**, com um módulo de carga em lote separado da aplicação web:

| Camada | Responsabilidade | Tecnologia |
| --- | --- | --- |
| Coleta | Baixar a 2ª fonte de polígonos (OSM) | Python, API Overpass |
| Carga (ETL) | Ler, cruzar, normalizar e gravar os dados | Python, Shapely (STRtree), PyMySQL |
| Persistência | Armazenar geometrias com índice espacial | MariaDB/MySQL (`GEOMETRY` + `SPATIAL INDEX`) |
| Backend | Expor os dados como GeoJSON via HTTP, com filtros, paginação e agregados | FastAPI, Pydantic, Uvicorn, PyMySQL |
| Frontend | Renderizar, filtrar e gerar relatório | React, Vite, TypeScript, MapLibre GL, deck.gl |
| Orquestração | Subir o ambiente local | Scripts Bash (`run.sh`, `db.sh`) |
| Testes | Validar filtros, contratos e endpoints | pytest, httpx |

**Componentes**

- **Coleta (`scripts/fetch_osm_buildings.py`)**: divide o município numa grade 6×6, consulta o Overpass célula a célula (com pausa de 8 s entre consultas), refaz em quadrantes menores o que falhar e grava um GeoJSON.
- **Carga (`import_data.py`)**: `load_buildings` (une e recorta o Overture), `load_osm_buildings`, `load_qg_points`, `match_points` e `relate_points_to_buildings` (junção espacial), `best_type` (cascata de classificação) e `main` (recria a tabela e insere em lotes de 500).
- **Backend**:
  - `main.py`: rotas, GZip e CORS;
  - `db.py`: conexão, validação do `bbox`, montagem do `WHERE`, consultas, agregados e conversão linha → Feature;
  - `schemas.py`: contratos Pydantic (feature leve, completa e estatísticas);
  - `config.py`: credenciais.
- **Frontend**:
  - `App.tsx`: mapa, camadas deck.gl, carga paginada com progresso, seleção, legenda e painel de detalhes;
  - `Report.tsx`: filtros, totais por tipo e por bairro, exportação para PDF;
  - `constants.ts`: ordem e cores dos tipos de uso, fonte única para mapa, legenda e relatório;
  - `main.tsx`: ponto de entrada; configura explicitamente o *worker* do MapLibre, que o Vite não empacotava (o mapa nascia em branco).

**Divisão de papéis no frontend**

| Biblioteca | Papel |
| --- | --- |
| React | Estado e interface (painéis, legenda, relatório) |
| MapLibre GL | Mapa base (OpenStreetMap), câmera e navegação |
| deck.gl | Renderização em massa via WebGL: polígonos, seleção por clique, extrusão 3D |

## API

| Método e rota | Descrição | Respostas |
| --- | --- | --- |
| `GET /` | Verificação de saúde (`{"status": "ok", "service": "atlas-urbano-api"}`) | 200 |
| `GET /api/buildings` | Edificações como `FeatureCollection` GeoJSON, com filtros e paginação opcionais (tabela abaixo). Sem parâmetros, devolve tudo de uma vez | 200, 422 |
| `GET /api/buildings/{building_id}` | Uma edificação (campos completos) como `Feature` GeoJSON | 200, 404 |
| `GET /api/stats` | Agregados (`total`, `by_tipo`, `by_bairro`, `area_total_m2`, `area_media_m2`) com os mesmos filtros | 200, 422 |

**Parâmetros de `GET /api/buildings`** (os filtros também valem para `/api/stats`, exceto `light`, `limit` e `offset`):

| Parâmetro | Descrição |
| --- | --- |
| `bbox` | `minLng,minLat,maxLng,maxLat`; filtra por retângulo usando o índice espacial (`MBRIntersects`) |
| `bairro` | Pode repetir para vários bairros |
| `tipo`, `fonte` | Filtros de igualdade |
| `light` | `true` devolve só `tipo`, `fonte` e `num_pavimentos`, suficiente para desenhar o mapa |
| `em_cobertura` | `true` esconde endereços sem polígono que estejam fora da janela de cobertura |
| `limit` | De 1 a 20.000 |
| `offset` | A partir de 0; a ordem é estável por `id` |

Respostas são comprimidas com GZip (acima de 1.000 bytes). Um `bbox` malformado, `limit` fora da faixa ou `offset` negativo devolvem 422.

**Propriedades de cada Feature**

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `id` | string | Código único do endereço (com sufixo `#n` se duplicado) ou ID do prédio (Overture, ou `osm-<id>`) |
| `area_m2` | number | Área aproximada em m², projetada localmente em torno do próprio prédio |
| `tipo` | string | `residencial`, `comercial`, `servico`, `religioso`, `institucional`, `hospedagem`, `agropecuario` ou `desconhecido` |
| `endereco` | string \| null | Logradouro e número (CNEFE) |
| `bairro` | string \| null | Localidade (CNEFE) |
| `estabelecimento` | string \| null | Descrição do estabelecimento (CNEFE) |
| `num_pavimentos` | number \| null | Pavimentos, quando o Overture informa |
| `fonte` | string \| null | Dataset de origem; `QG/CNEFE` indica endereço sem polígono, e `OpenStreetMap` indica polígono do fallback |

No modo `light`, a feature carrega apenas `tipo`, `fonte` e `num_pavimentos`.

## Modelo de dados

### Modelo atual (MVP)

Uma única tabela espacial, recriada a cada carga:

```
buildings(id, geom, area_m2, tipo, endereco, bairro,
          estabelecimento, num_pavimentos, fonte)
```

Todas as geometrias estão em **SRID 0** (coordenadas lon/lat sem sistema de referência declarado), o que limita o uso de funções geográficas nativas do banco. Há um `SPATIAL INDEX` em `geom`, usado pelo filtro `bbox`.

### Modelo-alvo (documentação)

A documentação define um modelo normalizado, a ser adotado nas próximas etapas:

| Entidade | Papel | Campos principais |
| --- | --- | --- |
| `NEIGHBORHOOD` | Bairro e estatísticas agregadas | nome, código IBGE do município, área total e mediana, nº de edificações e de endereços, densidade (edif./km²) |
| `CENSUS_TRACT` | Setor censitário | código do setor, município, tipo, geometria `MultiPolygon` (SRID 4674) |
| `BUILDING` | Telhado/edificação | `roof_geom` (4674), `utm_geom_24s` (31984), área, fonte primária, `source_confidence`, `source_agreement`, `verification_level` |
| `CNEFE_ADDRESS` | Endereço do CNEFE | código CNEFE, latitude/longitude, geometria `Point` (4674), logradouro, número, complemento, CEP, espécie |
| `SPATIAL_MATCH` | Associação N:M entre telhado e endereço | distância em metros, `is_exact_match`, `is_within_5m`, `is_within_10m`, `processed_at` |
| `FIELD_INSPECTION` | Conferência de campo | pontuação de prioridade, pavimentos observados, status, foto de referência, data |

```mermaid
erDiagram
    NEIGHBORHOOD ||--o{ CENSUS_TRACT : agrega
    NEIGHBORHOOD ||--o{ BUILDING : contem
    CENSUS_TRACT ||--o{ BUILDING : circunscreve
    CENSUS_TRACT ||--o{ CNEFE_ADDRESS : contem
    BUILDING ||--o{ SPATIAL_MATCH : origina
    CNEFE_ADDRESS ||--o{ SPATIAL_MATCH : origina
    BUILDING |o--o| FIELD_INSPECTION : priorizado_para
```

**Regras do modelo-alvo**

- **Um telhado para N endereços** (prédio vertical, lote com múltiplos endereços), resolvido pela tabela associativa `SPATIAL_MATCH`. No MVP, o mesmo polígono se repete em várias linhas, e o frontend reconhece essas linhas comparando a geometria (modo "Só o prédio selecionado").
- **Armazenar em 4674 (SIRGAS 2000), medir em 31984 (SIRGAS 2000 / UTM 24S)**: geometria canônica em graus, geometria projetada para cálculos de área e distância.
- `verification_level`: `automatico` → `conferido_tela` → `conferido_campo`.
- `source_agreement`: `concordam` / `divergem` / `so_uma_fonte`.

## Testes

Suíte em `backend/tests/test_api.py`, em níveis:

| Nível | O que cobre |
| --- | --- |
| Unitários puros | `parse_bbox` (formato, limites do planeta, mínimo < máximo), `build_where` (filtros combinados e uso do índice espacial) e conversores linha → Feature |
| Contrato | As features geradas passam na validação Pydantic de `schemas.py` |
| Regra de domínio | `best_type` do ETL (o QG prevalece sobre o Overture) |
| Endpoints | Com o banco simulado (`monkeypatch`): os filtros chegam à camada de dados, `bbox` inválido devolve 422 e id inexistente devolve 404 |
| Integração | Contra o MariaDB real; **pulados automaticamente** se o banco estiver fora do ar |

```bash
./.venv/bin/pip install pytest httpx      # dependências de desenvolvimento
./.venv/bin/python -m pytest backend/tests -q   # rodar da raiz do projeto
```

Os testes de integração de cobertura assumem os números da carga atual (87.951 registros) e precisam ser atualizados quando os dados mudarem.

## Requisitos e estado de implementação

A coluna **Estado** é uma avaliação do código atual (MVP) contra a documentação inicial.

### Requisitos funcionais

| ID | Requisito | Estado | Observação |
| --- | --- | --- | --- |
| RF01 | Baixar endereços (CNEFE) por município a partir do IBGE | Parcial | O arquivo é fornecido manualmente em `data/raw/qg/`; não há download automatizado |
| RF02 | Baixar malhas territoriais oficiais (setores e bairros) | Planejado | O bairro hoje vem do campo de localidade do CNEFE; o contorno do município é um arquivo manual |
| RF03 | Edificações de duas fontes independentes (Overture e Google Open Buildings) | Parcial | Overture + OpenStreetMap (fallback, em vez do Google Open Buildings); as fontes não são comparadas entre si |
| RF04 | Classificar cada endereço por espécie | Implementado | Mapeamento `ESPECIE_TO_TIPO` |
| RF05 | Associar cada endereço à edificação mais próxima, com raio documentado | Implementado | Contém → tolerância de ~15 m → mais próximo |
| RF06 | Campos de confiança (`confianca_fonte`, `concordancia_fontes`, `nivel_verificacao`, `prioridade_campo`) | Planejado | Exige comparar as fontes de polígono entre si |
| RF07 | Gerar e priorizar a fila de conferência de campo (`fila_conferencia.csv`) | Planejado | |
| RF08 | Tabela mestra de estatísticas por recorte territorial | Parcial | `/api/stats` já agrega total, por tipo, por bairro, área total e média; o relatório ainda calcula no navegador. Faltam mediana, densidade, endereços por edificação e % em construção |
| RF09 | Mapa interativo offline, com simbologia por densidade, faixa de área e endereços clusterizados | Parcial | Mapa interativo com cor por tipo e 3D próprio; usa tiles online e não tem clusterização nem simbologia por densidade ou área |
| RF10 | Usuário externo (não técnico) consulta o mapa e as estatísticas publicados | Parcial | Funciona localmente; ainda não há publicação |

### Requisitos não funcionais

| ID | Requisito | Categoria | Estado | Observação |
| --- | --- | --- | --- | --- |
| RNF01 | Custo total R$ 0,00 | Econômico | Atendido | Apenas dados e ferramentas abertos; tiles públicos do OSM |
| RNF02 | Reprodutibilidade a partir do pacote e das receitas | Manutenibilidade | Parcial | Há scripts, `requirements.txt` e testes, mas os dados brutos são manuais, a origem de parte deles não está documentada e a carga aponta para um banco diferente do script de subida |
| RNF03 | Cobertura de 100% do perímetro urbano processado | Completude | Parcial | Overture municipal (52.809 prédios) + fallback OSM (400); faltam os ~3,8 mil endereços ainda sem polígono |
| RNF04 | Taxa de associação endereço–edificação ≥ 85% (piloto: 93%) | Qualidade de dados | Atendido | 93,9% dos endereços caem em polígono (58.178 de 61.965) |
| RNF05 | Nenhum dado pessoal armazenado ou publicado | Privacidade | A verificar | Guarda-se endereço e estabelecimento; conferir se `estabelecimento` não expõe dados pessoais |
| RNF06 | Apenas fontes com licença compatível (vedados Google Maps/Street View, DNE dos Correios, Mapillary) | Legal | Atendido | Fontes em uso: OpenStreetMap, Overture e IBGE. O OSM é ODbL (exige atribuição e tem regras para bases derivadas); revisar antes de publicar (RF10) |
| RNF07 | Toda estatística publicada carrega fonte, método e limitação | Confiabilidade | Parcial | O painel de detalhes mostra a fonte por edificação; o relatório ainda não exibe método e limitação |

## Casos de uso

Atores: **Cliente** (consulta mapa e relatórios) e **Equipe Mantenedora** (carga, processamento e fila de conferência).

| Caso de uso | Ator | Estado |
| --- | --- | --- |
| Visualizar edificações no mapa | Cliente | Implementado (carga paginada, com progresso) |
| Filtrar por tipo de uso | Cliente | Implementado (no relatório) |
| Filtrar por bairro | Cliente | Implementado (no relatório) |
| Consultar dados agregados por bairro/setor | Cliente | Parcial (bairro sim; setor não) |
| Emitir relatório estatístico | Cliente | Implementado (exporta PDF pelo navegador) |
| Carregar a base de edificações e endereços | Equipe Mantenedora | Implementado (`import_data.py`, mais `fetch_osm_buildings.py` para a 2ª fonte) |
| Cruzar endereços × telhados | Equipe Mantenedora | Implementado (`relate_points_to_buildings` e `match_points`) |
| Gerar fila de conferência de campo | Equipe Mantenedora | Planejado |

## Decisões de engenharia

| Decisão | Por quê | Custo |
| --- | --- | --- |
| **ETL separado da API** | O cruzamento espacial é pesado e raro; a API é leve e constante. | Dados só mudam ao reexecutar a carga |
| **Índice espacial (STRtree) no ETL** | Evita comparação força-bruta entre ~62 mil pontos e dezenas de milhares de polígonos. | Índice em memória |
| **Vocabulário próprio de tipos de uso** | Isola o sistema dos códigos do IBGE e das classes do Overture/OSM (camada anticorrupção). | Mapeamentos a manter |
| **Cascata de fallback do tipo e da geometria** | Sempre existe um valor válido, e a fonte mais confiável prevalece (QG, depois Overture, depois OSM, depois círculo). | Prioridade fixa no código |
| **2ª fonte opcional** | Ausência do arquivo OSM só desliga o fallback, sem quebrar a carga. | Polígonos do OSM não são checados contra os do Overture |
| **Carga idempotente (`DROP` + recria)** | Rodar duas vezes dá o mesmo resultado, sem lixo acumulado. | Não é incremental; falha no meio deixa o banco vazio |
| **API como único acesso ao banco** | Credenciais nunca chegam ao navegador; permite trocar o banco sem tocar na interface. | Uma camada a mais |
| **GeoJSON como contrato** | Padrão aberto (RFC 7946), consumível por QGIS, Leaflet, deck.gl etc. | Verboso (mitigado com GZip) |
| **Filtros e paginação no servidor (`bbox`, `limit`/`offset`)** | A API deixa de ser "tudo ou nada"; o índice espacial passa a ser usado. | Paginação por `offset` fica lenta em páginas altas |
| **Payload leve (`light`) e completo** | O mapa só precisa de cor, filtro e altura; o detalhe vem inteiro. | Dois formatos a manter |
| **Agregação no banco (`/api/stats`)** | Evita baixar tudo para contar; o total alimenta a barra de progresso. | O relatório ainda não usa a rota |
| **Construtor de consulta separado da execução (`build_where`)** | Permite testar filtros sem banco. | |
| **Testes em níveis (unitário, contrato, endpoint, integração)** | Cobre os pontos críticos com custo baixo; a integração se desliga sozinha sem banco. | Cobertura parcial |
| **Compatibilidade retroativa da rota de listagem** | Sem parâmetros, responde como antes. | |
| **FastAPI** | Leve, tipado, com documentação automática; Django traria ORM e admin sem uso. | |
| **Consultas parametrizadas** | Protege contra injeção de SQL. | |
| **deck.gl sobre MapLibre** | WebGL aguenta dezenas de milhares de polígonos com seleção e extrusão; MapLibre é open source e dispensa chave de API. | Duas bibliotecas de mapa para integrar |
| **3D 100% próprio (deck.gl)** | Todo volume extrusado é uma feature nossa: tem a cor do tipo e, ao clicar, o endereço. Sem camada 3D externa. | Altura padrão de 5 m é ilustrativa (avisada na legenda) |
| **Carga paginada no frontend (5 mil por página) com progresso** | O mapa pinta aos poucos, sem congelar o navegador. | Ainda baixa a cidade inteira |
| **Estado local com hooks, dados derivados com `useMemo`** | O estado é pequeno; há uma única fonte de verdade (`data`) e o resto é derivado. | |
| **Retry e cancelamento no carregamento** | O backend pode estar subindo (5 tentativas para o total, 3 por página); o cancelamento evita atualizar um componente desmontado. | |
| **URL da API por variável de ambiente (`VITE_API_URL`)** | Sem endereço fixo no código do frontend. | |
| **PDF via `window.print()` + CSS `@media print`** | Gera o relatório sem biblioteca extra nem backend de relatórios. | Pouco controle de layout |
| **MariaDB local isolado por script** | Reprodutibilidade em ambiente restrito, sem exigir serviço instalado. | Depende de Linux/Bash e do `mariadbd` instalado |

**Recursos 3D:** prédios com `num_pavimentos` usam `pavimentos × 3 m` (dado do Overture); o restante usa altura ilustrativa de 5 m; as bolinhas ficam no plano. Incline a câmera (botão direito, arrastar) para ver.

**Modo "Só o prédio selecionado":** isola o prédio clicado e todos os endereços que compartilham o mesmo polígono (relação 1 telhado × N endereços), comparando a geometria.

## Limitações conhecidas

- **Credenciais**: `import_data.py` traz usuário, porta e senha escritos no arquivo, **diferentes** dos de `config.py` e do `db.sh`. Isso é um risco de segurança (se o repositório for público ou compartilhado, trocar a senha) e quebra o "rodar com um comando". Mover para variáveis de ambiente, numa configuração única.
- **OSM sem verificação de sobreposição**: os polígonos do OSM que não casam com nenhum endereço são inseridos sem checar se já existe um polígono do Overture no mesmo lugar, o que pode duplicar edificações (a contagem de 400 deve ser auditada).
- **"Edificação" é ambígua**: a tabela tem uma linha por endereço, então 87.951 registros não são 87.951 prédios. O relatório rotula a contagem como "Edificações".
- **Prédios sem endereço nem tipo** (~26 mil): o Overture municipal trouxe a forma, mas sem uso conhecido (ficam `desconhecido` até conferência de campo ou 2ª fonte com atributo).
- **Carga inicial ainda é a cidade inteira**: o frontend busca tudo em páginas de 5 mil features (~13 MB cada, antes do GZip), sem usar `bbox` nem `light`. Filtros e agregações do relatório rodam no navegador.
- **Custo no navegador**: a cada página carregada, o frontend recalcula uma chave de geometria (`JSON.stringify`) para todas as features, e o enquadramento inicial do mapa usa só a primeira página.
- **`em_cobertura` hoje não filtra nada**: a janela de cobertura (`JANELA_COBERTURA`, fixa no código) passou a cobrir o município inteiro.
- **Contrato Pydantic não ligado**: `schemas.py` é usado nos testes, mas as rotas não declaram `response_model`; a documentação em `/docs` não mostra o formato das respostas.
- **`MBRIntersects` é aproximado**: compara retângulos envolventes, então o filtro `bbox` pode trazer prédios que só encostam na área.
- **Estatísticas de área** incluem os círculos artificiais de ~5 m das bolinhas; o RF08 pede mediana, e hoje há só média.
- **Coleta do OSM**: o cache do `bbox` é lido, mas nunca gravado; só `ways` são consultados (relações com `building` são ignoradas); e quadrantes que falham na repescagem são descartados sem aviso final.
- **Origem de alguns dados não documentada**: Overture, CNEFE e o contorno do município são arquivos manuais (ver [Dados brutos](#dados-brutos-não-versionados)).
- **Acoplamento por *magic string***: o frontend identifica "endereço sem prédio" pelo valor `fonte = 'QG/CNEFE'`. Um campo explícito (ex.: `tem_poligono`) seria mais robusto.
- **ETL monolítico e destrutivo**: leitura, cruzamento, transformação e carga num único script, sem transação protegendo o estado anterior.
- **SRID 0** em todas as geometrias; a área é calculada no ETL por projeção local aproximada.
- **Heurística espacial simples**: em ponto ambíguo, escolhe o polígono mais próximo, sem tratar multiplicidade.
- **Testes parciais**: cobrem filtros, contratos e endpoints, mas não validam o cruzamento espacial do ETL (só a classificação `best_type`), e os de integração dependem dos números da carga atual.
- **Dependência de serviços externos de tiles** (OpenStreetMap), o que contraria o objetivo de mapa offline (RF09).

## Roadmap

Em ordem sugerida de prioridade:

1. **Segurança e configuração**: variáveis de ambiente únicas para banco e API, e trocar a credencial que está no código.
2. **Modelo de dados**: migrar para o modelo normalizado (`BUILDING`, `CNEFE_ADDRESS`, `SPATIAL_MATCH`), resolvendo a relação 1 telhado × N endereços; adotar SRID 4674 para armazenar e 31984 para medir.
3. **Qualidade do ETL**: carga em tabela de *staging* com troca atômica, deduplicação entre Overture e OSM, versões fixadas das dependências e testes do cruzamento espacial.
4. **Escala do frontend**: carregar por área visível (`bbox`) com o modo `light`, e buscar o detalhe sob demanda; avaliar *vector tiles* e migração para PostGIS.
5. **Confiança e conferência de campo**: comparar as fontes de polígono e calcular `confianca_fonte`, `concordancia_fontes`, `nivel_verificacao` e `prioridade_campo` (RF06); gerar `fila_conferencia.csv` (RF07).
6. **Estatísticas**: usar `/api/stats` no relatório; acrescentar mediana, densidade e % em construção (RF08), cada uma com fonte, método e limitação (RNF07); baixar as malhas oficiais de setores e bairros (RF02).
7. **API**: ligar `response_model` aos contratos Pydantic, e paginação por cursor.
8. **Mapa**: simbologia por densidade e faixa de área, clusterização de endereços e opção offline (RF09).
9. **Publicação**: disponibilizar mapa e estatísticas para usuários externos (RF10), com Docker Compose para simplificar a instalação e revisão da licença ODbL.

## Estrutura do repositório

```
backend/            API FastAPI (o frontend nunca acessa o MySQL diretamente)
  config.py         conexão/credenciais do banco
  db.py             filtros (bbox, bairro, tipo, fonte), consultas, agregados → GeoJSON
  main.py           rotas /, /api/buildings, /api/buildings/{id} e /api/stats
  schemas.py        contratos Pydantic (feature leve/completa, estatísticas)
  tests/
    test_api.py     testes unitários, de contrato, de endpoint e de integração
  requirements.txt  dependências Python do backend
frontend/           React + Vite + TS + MapLibre + deck.gl
  src/App.tsx       mapa, camadas, carga paginada, painel, legenda, relatório
  src/Report.tsx    relatório (totais, filtros, exportar PDF)
  src/constants.ts  cores e ordem dos tipos de uso
  src/index.css     estilos (inclui regras de impressão do relatório)
  src/main.tsx      ponto de entrada React (configura o worker do MapLibre)
scripts/
  db.sh             sobe/para o MariaDB local
  run.sh            sobe tudo (banco, importação, backend, frontend)
  mysql-local.cnf   tmpdir do MariaDB (sem /var/tmp no ambiente)
  fetch_osm_buildings.py   baixa polígonos do OSM (API Overpass) para data/raw/osm/
import_data.py      Overture + OSM + QG → relação espacial → tabela `buildings`
data/raw/           arquivos de dados (não versionados)
  overture/         edificações do Overture (janela e município)
  qg/               endereços do CNEFE
  osm/              polígonos do OSM (saída do script de coleta)
  municipio_boundary.geojson   contorno do município
```

## Pontos de extensão

A carga (`import_data.py`) e a rota `GET /api/buildings` (que já aceita filtros e paginação) são os lugares onde entram novas fontes de dados (importação IBGE/prefeitura) e novos filtros (por exemplo, por setor).