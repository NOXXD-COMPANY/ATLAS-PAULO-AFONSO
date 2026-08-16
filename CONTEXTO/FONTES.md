# Fontes de dados — catálogo verificado

> Todas gratuitas. URLs conferidas em **02/08/2026**. Cada ficha aponta a receita de acesso correspondente em [`RECEITAS.md`](./RECEITAS.md). Glossário de licenças em [`../CONTEXT.md`](../CONTEXT.md).

## Tabela-resumo

| Fonte | O que fornece | Licença | Receita |
|---|---|---|---|
| CNEFE / Censo 2022 (IBGE) | Todos os endereços do município, georreferenciados, com CEP e espécie | Dados públicos IBGE | R01, R09 |
| Dicionário CNEFE | Significado de cada coluna e dos códigos de espécie | Público | R02 |
| Malha de setores censitários 2022 | Polígonos oficiais de todos os setores da BA | Público | R03, R10 |
| Malha e agregados por bairros 2022 | Polígonos de bairros + estatísticas (onde houver) | Público | R04 |
| Agregados por setores censitários 2022 | Estatísticas do Censo por setor (domicílios, moradores) | Público | R05 |
| Overture Maps — buildings | Polígonos de edificações por bbox | ODbL | R06, R08 |
| Google Open Buildings v3 | Polígonos de edificações com área e confiança | CC BY 4.0 **ou** ODbL | R07, R15 |
| Open Buildings 2.5D Temporal | Altura e presença anual 2016–2023 (raster) — trilha avançada | CC BY 4.0 ou ODbL | — |
| Esri World Imagery | Basemap de satélite para conferência visual | Uso como fundo, com atribuição | fase F0 |
| OpenStreetMap | Vias e nomes de logradouros (apoio) | ODbL | — |
| IBGE Cidades | Números oficiais de referência do município | Público | consulta direta |

## Fichas

### CNEFE — Cadastro Nacional de Endereços para Fins Estatísticos (Censo 2022, IBGE)

- **O que é**: todos os endereços visitados no Censo 2022 — cerca de 106 milhões no Brasil — **100% georreferenciados**, com setor, quadra, face, CEP e espécie.
- **Arquivo do município** (1,7 MB):
  `https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/29_BA/2924009_PAULO_AFONSO.zip`
  (há também versão GeoJSON na pasta `GeoJSON/` do mesmo caminho)
- **Dicionário** (obrigatório ler antes de usar):
  `https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/Dicionario_CNEFE_Censo_2022.xls`
- **Pegadinhas**: CSV separado por `;`; conferir no dicionário os nomes exatos das colunas de coordenada, CEP e espécie antes de importar (R09). É retrato de 2022 — construções posteriores não aparecem.
- **É também a resposta ao "dados dos Correios"**: a base DNE dos Correios é paga; o CEP de cada endereço já vem aqui, de graça.

### Malha de setores censitários 2022 (IBGE)

- **Arquivo da Bahia** (GeoPackage, 111 MB):
  `https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/setores/gpkg/UF/BA/BA_setores_CD2022.gpkg`
  (também em `shp/` e `kml/` no mesmo caminho)
- **Uso**: filtrar `CD_MUN = '2924009'` e dissolver para obter o limite municipal (R10). O recorte por setor é o **plano B garantido** caso a malha de bairros não cubra o município.
- **Pegadinha**: 111 MB para a BA inteira — baixar uma vez, filtrar cedo, guardar só o recorte municipal em `dados-processados/`.

### Malha e agregados por bairros 2022 (IBGE)

- **Malha da Bahia** (Shapefile, 1,1 MB):
  `https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/bairros/shp/UF/BA_bairros_CD2022.zip`
- **Agregados por bairro** (CSV, Brasil inteiro, 13 temas):
  `https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Bairro_csv/`
- **Malha com atributos** (alternativa): `https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/malha_com_atributos/bairros/shp/BR/`
- **⚠️ Atenção**: o IBGE só publica bairros de municípios que os delimitaram formalmente e informaram — **a cobertura de Paulo Afonso NÃO está confirmada**. Verificar na Fase 1 (filtrar `CD_MUN = 2924009` no shapefile). Se não houver, o plano B está definido no [`PLANO-FASES.md`](./PLANO-FASES.md).

### Agregados por setores censitários 2022 (IBGE)

- **CSVs por tema** (usar o tema "Básico": domicílios e moradores por setor):
  `https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/`
- **Dicionário de dados**: arquivo `dicionario_de_dados_agregados_por_setores_censitarios_*.xlsx` na pasta-mãe.
- **Uso**: juntar à malha pelo código do setor e conferir os números do Atlas contra o Censo (endereços CNEFE × domicílios oficiais).

### Overture Maps — buildings

- **O que é**: base global aberta de polígonos de edificações (bilhões de footprints), agregando Microsoft, OpenStreetMap, Esri e outros, com estimativas de altura em parte das feições.
- **Acesso**: CLI oficial (documentação em `https://docs.overturemaps.org/`), receita R06.
- **Licença**: ODbL (contém dados OSM) — atribuir "Overture Maps Foundation / © OpenStreetMap contributors" e manter derivados abertos.
- **Pegadinha (Windows em português)**: o CLI grava o GeoJSON em codificação cp1252, o que quebra leitores UTF-8 — aplicar a receita R08 logo após o download.

### Google Open Buildings v3

- **O que é**: polígonos de edificações detectados por aprendizado de máquina em imagens de satélite, com `area_in_meters` e `confidence` por feição.
- **Acesso sem cadastro**: mapa clicável em `https://sites.research.google/open-buildings/` (clique na região para baixar a célula) ou URL direta:
  `https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_4_gzip/{CELULA}_buildings.csv.gz`
- **Formato**: CSV compactado por célula S2 nível 4, colunas `latitude, longitude, area_in_meters, confidence, geometry` (WKT) e `full_plus_code`.
- **Pegadinhas**: a célula que cobre a Bahia pode ter **gigabytes** — filtrar pelo bbox do município antes de abrir no QGIS (receita R15, DuckDB). Usar `confidence` nos filtros e reportá-la nos resultados.
- **Licença**: à escolha, CC BY 4.0 **ou** ODbL — escolher UMA, declarar no rodapé e manter a mesma no pacote inteiro.

### Google Open Buildings 2.5D Temporal (trilha avançada, opcional)

- **O que é**: rasters anuais 2016–2023 de presença, contagem e **altura** de edificações (~4 m de resolução efetiva).
- **Acesso**: `https://sites.research.google/gr/open-buildings/temporal/` — download direto do Cloud Storage documentado em notebook oficial (não exige Earth Engine).
- **Limitações**: é raster, não vetor; altura serve para distinguir térreo de sobrado, não para contar pavimentos. Nenhum entregável do projeto depende desta fonte — é enriquecimento.

### Esri World Imagery (basemap)

- **Uso**: fundo de satélite para conferência visual e auditoria amostral, adicionado no QGIS via QuickMapServices ou XYZ:
  `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`
- **Regras**: manter a atribuição "Esri, Maxar, Earthstar Geographics"; usar como **fundo**, não como fonte a vetorizar em massa.
- **Limitação**: em parte do interior da Bahia não há zoom máximo (19+) — concentrar a auditoria visual na área urbana.

### OpenStreetMap (apoio)

- **Uso**: vias, nomes de logradouros e polígonos de lugares como camada de apoio e rotulagem. Extratos regionais via Geofabrik (`https://download.geofabrik.de/`, recorte da região Nordeste — conferir o recorte disponível na Fase 0).
- **Licença**: ODbL — atribuir "© OpenStreetMap contributors".

### IBGE Cidades

- **Página do município**: `https://www.ibge.gov.br/cidades-e-estados/ba/paulo-afonso.html` — população 112.870 (Censo 2022), área territorial e demais números oficiais de referência.

### Fontes secundárias avançadas (citar como comunitárias)

- Espelhos **GeoParquet** do Google Open Buildings no source.coop (`https://source.coop/cholmes/google-open-buildings`) e o combinado Google+Microsoft da VIDA (`https://source.coop/vida/google-microsoft-open-buildings`) — consultáveis por DuckDB direto na nuvem. Úteis, mas de manutenção comunitária: usar como atalho, nunca como fonte primária citada.

## Fontes proibidas ou de uso restrito

| Fonte | Situação | Motivo |
|---|---|---|
| **Google Maps / Street View** | **PROIBIDA como fonte de dados** | Os Termos de Serviço vedam nominalmente traçar ou digitalizar contornos, extrair informação das imagens, criar modelos e baixar em massa. Não confundir com o Open Buildings acima, que é do Google Research sob licença aberta. |
| **DNE (Correios)** | Paga — não usar | O CEP de cada endereço já vem gratuitamente no CNEFE. |
| **Mapillary** | Restrita — evitar | Licença CC BY-SA (share-alike viral): qualquer derivado herda a licença. Preferir fotos próprias da equipe para conferência de campo. |
| **Google Earth Engine** | Desnecessária | Exige cadastro/autenticação e nada no projeto depende dela. |

## Linha de atribuição pronta (copiar no rodapé do mapa e do relatório)

> Fontes: IBGE — Censo Demográfico 2022 (CNEFE, malhas territoriais e agregados); Overture Maps Foundation / © OpenStreetMap contributors (ODbL); Google Research — Open Buildings v3 (CC BY 4.0); basemap Esri, Maxar, Earthstar Geographics. Elaboração: Atlas Urbano de Paulo Afonso — projeto de extensão universitária, 2026. Pegada de telhado não equivale a área construída; ver notas de método.
