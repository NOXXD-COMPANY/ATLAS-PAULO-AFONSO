# Atlas Urbano de Paulo Afonso — concepção

> Documento de concepção do projeto de extensão. Vocabulário e convenções em [`../CONTEXT.md`](../CONTEXT.md); plano do semestre em [`PLANO-FASES.md`](./PLANO-FASES.md); fontes em [`FONTES.md`](./FONTES.md); comandos em [`RECEITAS.md`](./RECEITAS.md).

## 1. Resumo

O Atlas Urbano de Paulo Afonso é um projeto de extensão universitária que produz, em um semestre e a custo zero, o primeiro retrato aberto e reprodutível do território construído do município: quantas edificações existem, de que tamanho, onde estão, quantos endereços há e de que tipo, e como tudo isso se distribui pelos bairros. O resultado é público: um mapa interativo, tabelas de estatísticas territoriais e uma memória metodológica que permite a qualquer pessoa refazer — e atualizar — o trabalho.

## 2. Motivação e perguntas norteadoras

O Brasil publicou nos últimos anos um conjunto inédito de dados territoriais abertos — os endereços georreferenciados do Censo 2022, malhas territoriais detalhadas e bases globais de edificações extraídas de satélite por aprendizado de máquina. Quase nenhuma cidade média brasileira, porém, tem esse material **combinado, conferido e apresentado** de forma útil. O projeto fecha essa lacuna para Paulo Afonso e, no caminho, forma estudantes em geoprocessamento, dados abertos e método.

Perguntas que o Atlas responde:

1. **Quantas edificações** existem em Paulo Afonso, e onde?
2. **De que tamanho** são (pegada de telhado), e como os tamanhos se distribuem?
3. **Quantos endereços** existem, e de que espécie (domicílios, estabelecimentos, em construção)?
4. **Como cada bairro se compara** — densidade construída, tamanho típico, endereços por edificação?
5. **O que os dados abertos não enxergam** — e com que confiança se pode afirmar cada número?

## 3. Objetivos

**Objetivo geral**: construir e publicar o inventário aberto de edificações e endereços de Paulo Afonso/BA, com estatísticas por recorte territorial e mapa interativo, usando exclusivamente dados públicos e ferramentas gratuitas.

**Objetivos específicos (mensuráveis)**:

1. Inventário municipal de **edificações** com área de pegada de telhado calculada para 100% da área urbana.
2. Base de **endereços** do CNEFE classificada por espécie, com contagem fechada para o município.
3. **Tabela mestra por bairro/setor**: nº de edificações, área somada e mediana de telhado, edificações/km², endereços por edificação, % de endereços "em construção".
4. **Mapa interativo** navegável em qualquer navegador + **memória metodológica** reprodutível (receitas + diário).
5. **Campos de confiança** em 100% das edificações (`confianca_fonte`, `concordancia_fontes`, `nivel_verificacao`, `prioridade_campo`) e **fila de conferência de campo** priorizada — o gratuito ordena, o campo afirma.

## 4. Escopo e não-escopo

**No escopo**: edificações (polígonos e áreas de telhado), endereços (pontos e espécies), recortes territoriais (bairros ou setores), estatísticas agregadas, comparação entre fontes de dados, mapa interativo, relatório de método.

**Fora do escopo — taxativo**:

- **Terrenos, lotes e limites de propriedade** — nenhuma fonte aberta os enxerga, e o projeto não os infere.
- **Qualquer uso fiscal ou administrativo** — o Atlas é retrato estatístico, não base para cobrança, fiscalização ou autuação de quem quer que seja.
- **Dados pessoais** — nenhum nome, CPF ou informação de morador entra no projeto (o CNEFE público já vem sem nomes).
- **Coleta porta a porta** — o projeto trabalha em gabinete; idas a campo são opcionais e apenas fotográficas, para conferência visual.
- **Valor, preço ou renda dos imóveis** — fora do escopo por completo.

## 5. Método em uma página

Pipeline de 5 etapas, executado com QGIS (trilha principal) ou Python/DuckDB (trilha opcional):

```
BAIXAR          →  LIMPAR           →  CRUZAR            →  AGREGAR           →  PUBLICAR
fontes oficiais    UTF-8, recorte      endereços ×          estatísticas por     mapa interativo
(IBGE, Overture,   municipal, ruído    edificações          bairro/setor         + tabelas +
Google, OSM)       fora, área em m²    (junção espacial)                          relatório
```

1. **Baixar** — CNEFE do município, malhas do IBGE (setores; bairros se houver), edificações do Overture Maps e do Google Open Buildings.
2. **Limpar** — corrigir codificação, recortar pelo limite municipal, remover polígonos-ruído (< 10 m²), calcular `area_m2` em projeção métrica.
3. **Cruzar** — associar cada edificação ao endereço mais próximo (raio documentado), comparar as duas fontes de edificações e escolher a primária com justificativa.
4. **Agregar** — produzir a tabela mestra por recorte territorial e conferir contra os agregados oficiais do Censo.
5. **Publicar** — mapa interativo, tabelas CSV, banner e relatório, tudo com atribuição de fontes e notas de limitação.

## 6. Fontes e ferramentas (resumo)

| Categoria | Escolha | Por quê |
|---|---|---|
| Endereços | **CNEFE / Censo 2022 (IBGE)** | 100% georreferenciado, com CEP e espécie, download por município |
| Recortes | **Malhas IBGE 2022** (setores; bairros a verificar) | Polígonos oficiais + estatísticas associadas |
| Edificações | **Overture Maps** × **Google Open Buildings v3** (comparar e escolher) | As duas maiores bases abertas de footprints; a comparação é parte do método |
| Basemap | **Esri World Imagery** | Referência visual para auditoria; uso permitido como fundo com atribuição |
| Ferramenta principal | **QGIS LTR** + plugins (QuickMapServices, qgis2web, DataPlotly) | Gratuito, gráfico, cobre o pipeline inteiro |
| Trilha opcional | **Python + DuckDB** | Filtrar bases gigantes e automatizar; caminho de crescimento para quem programa |

Catálogo completo, licenças e URLs verificadas: [`FONTES.md`](./FONTES.md).

## 7. Ética, licenças e limitações (resumo)

- **Fontes proibidas**: Google Maps/Street View (os Termos de Serviço vedam traçar contornos, extrair informação e baixar em massa); base DNE dos Correios (paga — o CEP já vem no CNEFE); Mapillary só com muito cuidado (licença share-alike viral).
- **Privacidade**: só dados públicos e agregados; em fotos de campo, sem rostos nem placas de veículos.
- **Honestidade metodológica**: pegada de telhado ≠ área construída; footprint ≠ limite de terreno; detecção automática tem teto de acurácia; o CNEFE é um retrato de 2022. Toda estatística publicada carrega a nota correspondente.

Detalhes na seção "Cuidados" do [`PLANO-FASES.md`](./PLANO-FASES.md) e no documento visual.

## 8. Critérios de qualidade

1. **Cobertura**: 100% do perímetro urbano com edificações e endereços processados.
2. **Associação endereço–edificação ≥ 85%** (referência do estudo piloto: 93%), com raio de busca documentado.
3. **Auditoria visual amostral**: ≥ 30 edificações conferidas contra o basemap por recorte analisado, com taxa de acerto registrada.
4. **Reprodutibilidade**: qualquer pessoa com o pacote final e as receitas refaz o resultado do zero.
5. **Transparência**: toda estatística publicada tem fonte, método e limitação declarados.
6. **Confiança explícita**: campos de confiança preenchidos em 100% das edificações publicadas; limiares e pesos documentados como decisão de método.

## 9. Resultados esperados

1. **`atlas_pa.gpkg`** — GeoPackage consolidado com todas as camadas padronizadas.
2. **Tabelas CSV** — tabela mestra por recorte + tabela de endereços por espécie + fila de conferência de campo (`fila_conferencia.csv`).
3. **`mapa/index.html`** — mapa interativo navegável offline em navegador comum.
4. **Banner e relatório de extensão** — no formato exigido pela instituição, alimentados pelo diário de bordo.
5. **Apresentação pública** — mostra de extensão ou equivalente, com o mapa ao vivo.
