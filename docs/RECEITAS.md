# Receitas — cookbook de comandos

> Cada receita tem: **objetivo → pré-requisitos → passos → saída esperada → erros comuns**. As fases do [`PLANO-FASES.md`](./PLANO-FASES.md) citam as receitas pelo número. URLs completas e licenças em [`FONTES.md`](./FONTES.md).
>
> ⚠️ **Sobre bboxes**: os valores `-38.35,-9.55,-38.05,-9.30` usados nos exemplos são **aproximados** (núcleo urbano). Extraia o bbox real do limite municipal (R10): clique direito na camada `limite_municipal` → Propriedades → Informação → Extensão.

---

## A. Downloads

### R01 — Baixar o CNEFE do município

- **Objetivo**: obter todos os endereços georreferenciados de Paulo Afonso.
- **Pré-requisitos**: navegador ou terminal com `curl`.
- **Passos**:
  ```
  curl -L -o dados-brutos/2924009_PAULO_AFONSO.zip "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/29_BA/2924009_PAULO_AFONSO.zip"
  ```
  Descompactar o zip dentro de `dados-brutos/`.
- **Saída esperada**: zip de ~1,7 MB com um CSV de dezenas de milhares de linhas (1 linha = 1 endereço).
- **Erros comuns**: FTP do IBGE fora do ar (tentar mais tarde; por isso baixamos tudo cedo e espelhamos no drive da equipe).

### R02 — Baixar o dicionário do CNEFE

- **Objetivo**: saber o que significa cada coluna e cada código de espécie.
- **Passos**:
  ```
  curl -L -o dados-brutos/Dicionario_CNEFE_Censo_2022.xls "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/Dicionario_CNEFE_Censo_2022.xls"
  ```
  Abrir no LibreOffice/Excel e **ler antes de importar o CSV**.
- **Saída esperada**: planilha com nome, tipo e descrição de cada coluna (coordenadas, CEP, espécie, setor, quadra, face).
- **Erros comuns**: pular esta receita e adivinhar colunas — não adivinhe.

### R03 — Baixar a malha de setores censitários da BA

- **Objetivo**: obter os polígonos oficiais dos setores (base do limite municipal e do plano B de recorte).
- **Passos**:
  ```
  curl -L -o dados-brutos/BA_setores_CD2022.gpkg "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/setores/gpkg/UF/BA/BA_setores_CD2022.gpkg"
  ```
- **Saída esperada**: GeoPackage de ~111 MB (Bahia inteira).
- **Erros comuns**: tentar abrir tudo e travar máquina modesta — aplicar o filtro da R10 logo após abrir.

### R04 — Baixar malha de bairros da BA + agregados por bairro

- **Objetivo**: verificar se Paulo Afonso tem bairros oficiais do IBGE e, se tiver, usá-los como recorte.
- **Passos**:
  ```
  curl -L -o dados-brutos/BA_bairros_CD2022.zip "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/bairros/shp/UF/BA_bairros_CD2022.zip"
  ```
  Descompactar, abrir no QGIS e filtrar (`Ctrl+F` na camada): `"CD_MUN" = '2924009'`.
  Agregados (estatísticas por bairro, Brasil inteiro): navegar em `https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Bairro_csv/` e baixar o tema Básico.
- **Saída esperada**: OU polígonos de bairros de Paulo Afonso (adotar como recorte oficial) OU zero feições (ativar o plano B do PLANO-FASES).
- **Erros comuns**: concluir "não tem bairro" por erro de filtro — conferir se o campo se chama `CD_MUN` na tabela de atributos antes de decidir.

### R05 — Baixar agregados por setor censitário (tema Básico)

- **Objetivo**: obter domicílios e moradores por setor para conferir o Atlas contra o Censo.
- **Passos**: navegar em `https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/`, baixar o tema **Básico** e o dicionário (`dicionario_de_dados_agregados_por_setores_censitarios_*.xlsx`) da pasta-mãe. Filtrar as linhas cujo código de setor começa com `2924009`.
- **Saída esperada**: CSV com 1 linha por setor do município, com totais de domicílios e moradores.
- **Erros comuns**: juntar pelo campo errado — a chave é o código do setor (confira o nome exato no dicionário), não o nome.

### R06 — Baixar edificações do Overture Maps

- **Objetivo**: obter os polígonos de edificações da área de interesse.
- **Pré-requisitos**: Python 3 instalado.
- **Passos**:
  ```
  pip install overturemaps
  overturemaps download --bbox=-38.35,-9.55,-38.05,-9.30 -f geojson --type=building -o dados-brutos/edificacoes_overture.geojson
  ```
  (bbox aproximado — substituir pelo bbox real do limite municipal, R10)
- **Saída esperada**: GeoJSON com dezenas de milhares de polígonos.
- **Erros comuns**: **no Windows em português o arquivo sai em cp1252** e quebra o QGIS/parsers → aplicar R08 imediatamente. Download demora em conexão lenta — é normal.

### R07 — Baixar Google Open Buildings v3

- **Objetivo**: obter a segunda fonte de edificações (com `area_in_meters` e `confidence`).
- **Passos**: abrir `https://sites.research.google/open-buildings/`, ativar o painel de download, clicar na região de Paulo Afonso e baixar o CSV da célula S2 indicada. Alternativa direta (o nome da célula aparece no site):
  ```
  curl -L -o dados-brutos/CELULA_buildings.csv.gz "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_4_gzip/CELULA_buildings.csv.gz"
  ```
- **Saída esperada**: CSV compactado (pode ter **gigabytes** — a célula cobre uma região enorme).
- **Erros comuns**: tentar abrir o CSV inteiro no QGIS/Excel → usar R15 (DuckDB) para filtrar pelo bbox antes; ou trabalhar com a versão em GeoParquet do source.coop (ficha em FONTES.md).

---

## B. Conversões e limpeza

### R08 — Corrigir codificação cp1252 → UTF-8 (Windows pt-BR)

- **Objetivo**: consertar o GeoJSON do Overture que sai com codificação errada no Windows em português.
- **Passos**:
  ```
  python -c "open('dados-processados/edificacoes_overture_utf8.geojson','w',encoding='utf-8').write(open('dados-brutos/edificacoes_overture.geojson',encoding='cp1252').read())"
  ```
- **Saída esperada**: arquivo novo que abre no QGIS sem erro de parser.
- **Erros comuns**: sobrescrever o bruto (nunca — a convenção é bruto intocado); aplicar a conversão duas vezes sobre o mesmo arquivo (a segunda leitura trata o UTF-8 como cp1252 e corrompe os acentos — sempre partir do bruto).

### R09 — Importar o CSV do CNEFE no QGIS

- **Objetivo**: transformar o CSV de endereços em camada de pontos.
- **Passos**: QGIS → `Camada → Adicionar camada → Adicionar camada de texto delimitado`. Configurar: separador **`;`**; codificação UTF-8; campo X = coluna de **longitude**, campo Y = coluna de **latitude** (nomes exatos no dicionário, R02); CRS **EPSG:4674**. Salvar como camada `enderecos_cnefe` no GeoPackage do projeto.
- **Saída esperada**: nuvem de pontos cobrindo a cidade (e a zona rural).
- **Erros comuns**: inverter X e Y (a cidade "aparece no oceano Índico" — X é longitude, negativa ~ -38); esquecer o CRS e cair em WGS84 sem perceber (para este projeto a diferença é irrelevante na prática, mas a convenção é 4674).

### R10 — Recorte municipal: filtrar setores e dissolver o limite

- **Objetivo**: obter `limite_municipal` e `setores_2022` só de Paulo Afonso.
- **Passos**:
  1. Abrir `BA_setores_CD2022.gpkg` no QGIS.
  2. Filtrar a camada: `"CD_MUN" = '2924009'` → salvar como `setores_2022`.
  3. `Vetor → Ferramentas de geoprocessamento → Dissolver` sobre `setores_2022` → salvar como `limite_municipal`.
  4. Anotar o **bbox real**: clique direito em `limite_municipal` → Propriedades → Informação → Extensão.
- **Saída esperada**: um polígono único do município + a malha de setores interna.
- **Erros comuns**: filtrar com número em vez de texto (o campo é texto: use aspas simples no valor).

### R11 — Recortar edificações pelo limite municipal

- **Objetivo**: manter apenas as edificações dentro do município.
- **Passos**: `Vetor → Ferramentas de geoprocessamento → Recortar` — entrada: camada de edificações; camada de sobreposição: `limite_municipal`. Salvar como `edificacoes` no GeoPackage.
- **Saída esperada**: camada de edificações sem os vizinhos (Glória/BA, Delmiro Gouveia/AL etc.).
- **Erros comuns**: recortar o bruto e jogar fora o original — o recorte é um arquivo novo em `dados-processados/`.

### R12 — Calcular a área de telhado em m²

- **Objetivo**: coluna `area_m2` correta para cada edificação.
- **Passos**:
  1. `Processamento → Caixa de ferramentas → Reprojetar camada` → CRS de destino **EPSG:31984** (SIRGAS 2000 / UTM 24S).
  2. Na camada reprojetada: `Calculadora de campo` → novo campo `area_m2` (decimal) → expressão `$area`.
  3. Limpar ruído: filtrar/excluir `area_m2 < 10` (registrar quantas feições saíram).
- **Saída esperada**: mediana municipal na casa de ~100 m² (referência do estudo piloto: 112 m²).
- **Erros comuns**: calcular `$area` na camada em graus (EPSG:4674) — dá números minúsculos e sem sentido; sempre reprojetar antes.

---

## C. Análise

### R13 — Junção espacial endereço ↔ edificação

- **Objetivo**: associar cada edificação ao(s) endereço(s) correspondente(s).
- **Passos**: `Processamento → Caixa de ferramentas → Unir atributos pelo vizinho mais próximo` — camada base: `edificacoes`; camada de junção: `enderecos_cnefe`; **distância máxima: começar com 25 m** (testar 50 m e comparar); vizinhos: 1. Salvar como `edificacoes_enderecadas`. Calcular a taxa: nº de edificações com endereço associado ÷ total.
- **Saída esperada**: taxa ≥ 85% na área urbana (piloto de referência: 93%).
- **Erros comuns**: não registrar o raio usado (o número final muda com ele — é decisão de método, vai no diário e no relatório); esquecer que 1 prédio tem N endereços (a contagem "endereços por edificação" usa a junção inversa: pontos dentro/próximos do polígono).

### R14 — Estatísticas por recorte territorial

- **Objetivo**: montar a tabela mestra por bairro (ou setor).
- **Passos**:
  - `Contar pontos no polígono` (endereços por recorte, total e por espécie — rodar com filtro por espécie).
  - `Unir atributos por localização (resumo)` — edificações dentro de cada recorte, estatísticas de `area_m2`: contagem, soma, mediana.
  - Calculadora de campo no recorte: `edif_km2 = contagem / ($area / 1000000)` (com o recorte em EPSG:31984).
  - Exportar a tabela final: clique direito na camada → Exportar → CSV.
- **Saída esperada**: 1 linha por recorte com: nº edificações, área somada, mediana, edif./km², endereços, endereços/edificação, % em construção.
- **Erros comuns**: misturar recortes (metade das métricas por bairro, metade por setor) — escolher o recorte na F1 e manter.

### R15 — DuckDB: filtrar o CSV gigante do Google v3 (trilha opcional)

- **Objetivo**: extrair só o bbox de interesse de um CSV de gigabytes, sem estourar a RAM.
- **Pré-requisitos**: DuckDB CLI (download único em `https://duckdb.org`).
- **Passos** (no prompt do DuckDB, ajustando nome da célula e bbox):
  ```sql
  INSTALL spatial; LOAD spatial;
  CREATE TABLE ed AS
    SELECT * FROM read_csv_auto('dados-brutos/CELULA_buildings.csv.gz')
    WHERE longitude BETWEEN -38.35 AND -38.05
      AND latitude  BETWEEN  -9.55 AND  -9.30;
  COPY (SELECT latitude, longitude, area_in_meters, confidence,
               ST_GeomFromText(geometry) AS geom
        FROM ed)
  TO 'dados-processados/edificacoes_google.geojson'
  WITH (FORMAT GDAL, DRIVER 'GeoJSON');
  ```
- **Saída esperada**: GeoJSON local pequeno, pronto para o QGIS.
- **Erros comuns**: esquecer `INSTALL spatial`; usar o bbox aproximado no produto final (vale para explorar; o oficial usa o bbox real da R10).

### R16 — Histograma de áreas de telhado

- **Objetivo**: visualizar a distribuição de tamanhos (sustenta a "mediana" do relatório).
- **Passos**: instalar o plugin **DataPlotly** no QGIS → gráfico tipo histograma → camada `edificacoes` → campo `area_m2` → limitar eixo X a 0–500 m² para leitura.
- **Saída esperada**: distribuição assimétrica com pico perto da mediana (~100 m²) e cauda longa (galpões, escolas).
- **Erros comuns**: reportar a média em vez da mediana — a cauda longa distorce a média; o projeto reporta mediana.

---

## D. Publicação

### R17 — Exportar o mapa interativo (qgis2web)

- **Objetivo**: gerar `mapa/index.html` navegável em qualquer navegador.
- **Passos**: instalar o plugin **qgis2web** → `Internet → qgis2web → Create web map` → motor **Leaflet** → conferir camadas visíveis, popups (campos `area_m2`, espécie) e cluster para endereços → Export para a pasta `mapa/`.
- **Saída esperada**: pasta com `index.html` + recursos, abrindo offline com legenda e controle de camadas.
- **Erros comuns**: exportar as camadas completas sem simplificar (R19) e gerar um mapa de centenas de MB; esquecer a linha de atribuição (R20).

### R18 — Alternativa em Python (folium)

- **Objetivo**: o mesmo mapa, para quem preferir código.
- **Passos**:
  ```python
  # pip install folium
  import folium
  m = folium.Map(location=[-9.40, -38.22], zoom_start=13, tiles=None)
  folium.TileLayer(
      tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      attr="Esri, Maxar, Earthstar Geographics", name="Satélite").add_to(m)
  folium.GeoJson("dados-processados/edificacoes.geojson", name="Edificações").add_to(m)
  folium.LayerControl().add_to(m)
  m.save("mapa/index.html")
  ```
- **Saída esperada**: `mapa/index.html` equivalente ao da R17.
- **Erros comuns**: carregar o GeoJSON completo de edificações (pesado) — usar a versão simplificada da R19.

### R19 — Simplificar para a web

- **Objetivo**: mapa leve (< 25 MB de meta, < 60 MB de teto).
- **Passos**: `Vetor → Ferramentas de geometria → Simplificar` (tolerância inicial 0,00001 grau) para os polígonos; para zoom baixo, usar `Centroides` das edificações em vez dos polígonos; ativar cluster nos pontos de endereço (opção do qgis2web/folium); arredondar coordenadas para 6 casas.
- **Saída esperada**: mesma leitura visual com fração do tamanho.
- **Erros comuns**: simplificar demais e criar sobreposições visíveis — conferir 2–3 quadras no zoom máximo após simplificar.

### R20 — Checklist de atribuição e publicação

- **Objetivo**: nenhum produto sai sem crédito e sem nota de método.
- **Passos** — conferir antes de publicar qualquer mapa, tabela ou slide:
  1. Linha de atribuição completa (pronta em [`FONTES.md`](./FONTES.md)) visível no rodapé.
  2. Licença escolhida do Open Buildings declarada (CC BY 4.0 **ou** ODbL, a mesma em tudo).
  3. Nota "pegada de telhado ≠ área construída" presente.
  4. Taxa de associação e raio da R13 reportados.
  5. Data dos dados (Censo 2022; versão/data do download das edificações) declarada.
  6. Nada de dado pessoal, nome de morador ou endereço individual em destaque.
- **Saída esperada**: publicação que sobrevive a qualquer questionamento de origem e método.
- **Erros comuns**: atribuir só o IBGE e esquecer Overture/OSM/Google — as licenças abertas **exigem** o crédito.

---

## E. Confiança e conferência de campo

### R21 — Concordância entre fontes (primária × secundária)

- **Objetivo**: medir, edificação por edificação, se as duas fontes independentes (Overture e Google) desenham a mesma coisa — o sinal de confiança mais forte disponível de graça.
- **Pré-requisitos**: fonte primária escolhida na F2 como camada `edificacoes` (com `area_m2`, R12); fonte secundária recortada pelo limite municipal (R11); **ambas reprojetadas em EPSG:31984**.
- **Passos**:
  1. `Vetor → Ferramentas de geoprocessamento → Interseção` — entrada: `edificacoes`; camada de sobreposição: a fonte secundária → gera a camada `intersecao`.
  2. Na `intersecao`: calculadora de campo → `area_int` = `$area`.
  3. `Unir atributos por localização (resumo)` — na `edificacoes`, somar `area_int` das interseções. O QGIS nomeia o campo somado automaticamente (ex.: `area_int_sum`): renomeie para `area_sobreposta` ou ajuste o nome na expressão do passo 4.
  4. Calculadora de campo em `edificacoes` → campo texto `concordancia_fontes`:
     ```
     CASE
       WHEN "area_sobreposta" IS NULL OR "area_sobreposta" = 0 THEN 'so_uma_fonte'
       WHEN "area_sobreposta" / "area_m2" >= 0.6 THEN 'concordam'
       ELSE 'divergem'
     END
     ```
     O limiar de 60% de sobreposição é **decisão de método** (como o raio da R13): registrar no diário e manter o mesmo no projeto inteiro.
- **Saída esperada**: maioria `concordam` na área urbana consolidada; `so_uma_fonte` concentrado em anexos pequenos e construções recentes; `divergem` onde uma fonte fundiu casas geminadas e a outra não.
- **Erros comuns**: calcular em graus (sempre EPSG:31984); esquecer de recortar a secundária antes (aparecem interseções fora do município); tratar o limiar como norma — é escolha documentável, não verdade.

### R22 — Campos de confiança e fila de conferência de campo

- **Objetivo**: criar `confianca_fonte`, `nivel_verificacao` e `prioridade_campo` e exportar a fila do que merece visita in loco.
- **Pré-requisitos**: R12 (`area_m2`), R13 (associação de endereço), R21 (`concordancia_fontes`).
- **Passos**:
  1. Campos novos em `edificacoes`: `confianca_fonte` (decimal — se a fonte primária for o Google v3, copiar de `confidence`; se for o Overture, deixar NULO e usar a concordância como sinal principal), `nivel_verificacao` (texto, inicializar com `'automatico'`) e `prioridade_campo` (inteiro).
  2. Calculadora de campo → `prioridade_campo`, somando sinais de alerta (**ajuste os nomes dos campos unidos na R13 aos da sua camada**; o código de "em construção" está no dicionário da R02):
     ```
     (CASE WHEN "concordancia_fontes" = 'so_uma_fonte' THEN 3
           WHEN "concordancia_fontes" = 'divergem'     THEN 2 ELSE 0 END)
     + (CASE WHEN "confianca_fonte" IS NOT NULL AND "confianca_fonte" < 0.75 THEN 2 ELSE 0 END)
     + (CASE WHEN "area_m2" > 600 OR "area_m2" < 15 THEN 1 ELSE 0 END)
     + (CASE WHEN <campo do endereço unido na R13> IS NULL THEN 1 ELSE 0 END)
     + (CASE WHEN <espécie do endereço unido> = <código "em construção"> THEN 1 ELSE 0 END)
     ```
  3. Escada de verificação: a auditoria visual da F3 muda `nivel_verificacao` para `'conferido_tela'` nas edificações conferidas contra o satélite; a visita de campo (com foto) muda para `'conferido_campo'` — **o único degrau que autoriza falar em certeza**. Na visita, anotar `pavimentos_observados`; daí `area_construida_estimada = area_m2 * pavimentos_observados` (SEMPRE rotulada como estimativa).
  4. Fila: ordenar `prioridade_campo` em ordem decrescente e exportar `fila_conferencia.csv` (id, endereço, bairro, `area_m2`, `prioridade_campo` e, se quiser, quais sinais pesaram — os termos do passo 2).
- **Saída esperada**: maioria das edificações com score 0–1; topo da fila com centenas de casos, não milhares — é lá que as visitas valem a pena.
- **Erros comuns**: tratar o score como veredito (é ordenação de dúvida, não prova de erro); esquecer de atualizar `nivel_verificacao` depois da auditoria (a escada passa a mentir); mudar os pesos no meio do projeto sem registrar no diário.
