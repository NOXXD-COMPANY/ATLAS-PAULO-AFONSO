# Atlas Urbano de Paulo Afonso

Projeto de **extensão universitária** que constrói, em um semestre, o inventário aberto de **edificações, endereços e estatísticas territoriais** de Paulo Afonso/BA — usando exclusivamente dados públicos e ferramentas gratuitas.

> Este arquivo reúne o glossário e as convenções da equipe. A concepção completa está em [`docs/CONCEPCAO.md`](./docs/CONCEPCAO.md); o plano do semestre em [`docs/PLANO-FASES.md`](./docs/PLANO-FASES.md); as fontes de dados em [`docs/FONTES.md`](./docs/FONTES.md); os comandos prontos em [`docs/RECEITAS.md`](./docs/RECEITAS.md).

## Identificação

| Campo | Valor |
|---|---|
| Natureza | Projeto de extensão universitária |
| Duração | 1 semestre letivo (~16 semanas, adaptável) |
| Equipe | 4 a 8 estudantes + orientador(a) |
| Cidade-alvo | Paulo Afonso/BA |
| Código IBGE | 2924009 |
| População | 112.870 habitantes (Censo 2022) |
| Custo | R$ 0,00 — todas as fontes e ferramentas são gratuitas |

## O que é / o que não é

**É**: um retrato aberto e reprodutível da cidade — quantas edificações existem, de que tamanho, onde estão, como se distribuem os endereços por tipo — publicado como mapa interativo, tabelas e relatório de método.

**Não é**: base oficial de nenhum órgão. O projeto **não** trata de terrenos ou limites de propriedade, **não** usa dados pessoais e **não** serve de fundamento para qualquer decisão administrativa.

## Glossário

**Edificação**:
Objeto físico construído sobre o território — casa, prédio, galpão, escola. É o que as imagens de satélite conseguem ver e o que o projeto inventaria.

**Pegada de telhado (footprint)**:
Polígono da projeção da cobertura vista de cima. É um **indício** de ocupação e a medida que o projeto calcula.
_Evitar_: "área do imóvel", "área da casa".

**Área construída**:
Soma das áreas de **todos os pavimentos** (NBR 12721). **Não é observável de cima**: um sobrado de 200 m² construídos pode ter 100 m² de telhado. O projeto mede pegada de telhado, nunca área construída — confundir as duas é o erro metodológico nº 1 a evitar.

**Endereço**:
Ponto georreferenciado do CNEFE com logradouro, número, CEP e espécie. Um endereço não é uma edificação: um prédio tem 1 telhado e dezenas de endereços.

**Espécie (CNEFE)**:
Classificação do endereço no Censo: domicílio particular, domicílio coletivo, estabelecimento (agropecuário, de ensino, de saúde, religioso, de outras finalidades) e **edificação em construção ou reforma**. Os códigos exatos estão no dicionário oficial (receita R02).

**Setor censitário**:
Menor unidade territorial de coleta do IBGE, com polígono oficial e estatísticas associadas. É o recorte garantido do projeto — sempre existe.

**Quadra e face**:
Subdivisões do setor no CNEFE urbano: a quadra é o quarteirão; a face é um dos lados da quadra.

**Bairro**:
Recorte territorial com nome de uso local. O IBGE publicou malha de bairros do Censo 2022 **apenas para municípios que os delimitaram formalmente** — a cobertura de Paulo Afonso é uma verificação da Fase 1 (com plano B definido).

**CEP**:
Código de Endereçamento Postal. A base completa dos Correios (DNE) é **paga**; o CEP de cada endereço já vem gratuitamente no CNEFE — é assim que o projeto o obtém.

**Geocodificação**:
Transformar um endereço em coordenada (ou o contrário). No projeto, o CNEFE já vem geocodificado — o trabalho é de conferência, não de geocodificação.

**Junção espacial**:
Operação que relaciona duas camadas pela posição geográfica (ex.: "qual o endereço mais próximo desta edificação?"). É o coração da Fase 3.

**Concordância entre fontes**:
Grau em que as duas bases independentes de edificações (Overture e Google) desenham a mesma coisa no mesmo lugar: `concordam`, `divergem` ou `so_uma_fonte`. Dois detectores independentes concordando é o sinal de confiança mais forte que existe de graça.

**Nível de verificação**:
Escada de quem já olhou para a edificação: `automatico` (veio da fonte, ninguém olhou) → `conferido_tela` (auditada contra o satélite) → `conferido_campo` (visitada, com foto). **Só o último degrau autoriza falar em certeza** — o dado gratuito ordena, o campo afirma.

**Fila de conferência**:
Lista de edificações ordenada por `prioridade_campo` (score de sinais de alerta: fontes discordando, confiança baixa, polígono anômalo, sem endereço associado). Diz onde a visita in loco vale a pena.

**Célula S2**:
Sistema de divisão do globo em células usado pelo Google Open Buildings para particionar os downloads. Paulo Afonso cai inteira em uma célula de nível 4.

**Bbox**:
Retângulo delimitador (W,S,E,N em graus) usado para recortar downloads. Os bboxes dos exemplos são **aproximados** — extraia o real do limite municipal no QGIS.

**CRS (Sistema de Referência de Coordenadas)**:
- **EPSG:4674** — SIRGAS 2000 geográfico: padrão brasileiro, usado para **armazenar**.
- **EPSG:31984** — SIRGAS 2000 / UTM zona 24S: métrico, usado para **medir área e distância** (Paulo Afonso está na zona 24S).
- **EPSG:3857** — Web Mercator: usado pelos mapas web; o QGIS converte sozinho.

**Formatos**:
- **CSV** — tabela texto; vira camada de pontos quando tem latitude/longitude.
- **GeoJSON** — vetor em texto, bom para web; sempre em UTF-8.
- **GeoPackage (GPKG)** — banco SQLite com camadas vetoriais; o formato de trabalho do projeto.
- **Shapefile (SHP)** — formato legado do IBGE (vários arquivos por camada); converter para GPKG ao importar.
- **GeoParquet** — colunar, eficiente para bases enormes; aparece só na trilha avançada.

**Basemap**:
Camada de fundo (imagem de satélite ou mapa de ruas) usada como **referência visual e de auditoria** — nunca como fonte de dados a vetorizar.

**Licenças**:
- **Dados públicos IBGE** — uso livre com citação da fonte e ano.
- **ODbL** — licença aberta com atribuição e compartilhamento pela mesma licença para bases derivadas (Overture/OSM).
- **CC BY 4.0** — uso livre com atribuição (Google Open Buildings, à escolha).
- **CC BY-SA** — atribuição + share-alike **viral**: o derivado herda a licença (caso Mapillary — por isso, evitar).

## Convenções da equipe

1. **CRS**: armazenar tudo em EPSG:4674; medir área/distância sempre em EPSG:31984. Nunca medir em coordenadas geográficas.
2. **Camadas com nomes padronizados**: `limite_municipal`, `setores_2022`, `bairros`, `enderecos_cnefe`, `edificacoes`, `edificacoes_enderecadas`.
3. **Pastas**: `dados-brutos/` (o que foi baixado, intocado) separado de `dados-processados/` (o que a equipe produziu). **Nunca editar arquivo bruto** — refazer a partir dele.
4. **Nomes de arquivo com data**: `AAAA-MM-DD_descricao` (ex.: `2026-08-15_edificacoes_overture_utf8.geojson`).
5. **Codificação UTF-8 sempre** — atenção especial no Windows em português (receita R08).
6. **Toda decisão registrada** no diário de bordo (modelo em `docs/DIARIO-MODELO.md`): qual fonte foi escolhida, qual raio de junção, o que ficou de fora e por quê.
7. **Todo número publicado sai acompanhado** da fonte, do método e da limitação — sem exceção.
8. **Campos de confiança padronizados** na camada `edificacoes`: `confianca_fonte`, `concordancia_fontes`, `nivel_verificacao`, `prioridade_campo` (receitas R21 e R22). Nenhuma edificação publicada sem eles; limiares e pesos (raio da junção, sobreposição de 60%, pontos do score) são decisões de método registradas no diário.

## Números de referência

- **112.870 habitantes** (Censo 2022) e **código IBGE 2924009** — âncoras oficiais do município.
- **Estudo piloto de referência** (um bairro de ~1,75 km²): ~1.100 edificações, ~640 edificações/km², telhado mediano ~112 m², **93% de associação automática endereço–edificação**. Use como calibração de expectativa: se seus resultados fugirem muito dessas ordens de grandeza, investigue antes de seguir.
- **Expectativa de planejamento para o município**: dezenas de milhares de edificações (30–60 mil, a confirmar na Fase 2).
- **Metas de qualidade**: associação endereço–edificação ≥ 85%; auditoria visual amostral de ≥ 30 edificações por recorte analisado.
