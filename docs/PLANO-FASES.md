# Plano de fases — um semestre letivo

> Plano de execução do Atlas Urbano de Paulo Afonso para uma equipe de 4 a 8 estudantes, em ~16 semanas (adaptável). As receitas citadas (R01…R22) estão em [`RECEITAS.md`](./RECEITAS.md); as fontes em [`FONTES.md`](./FONTES.md); convenções em [`../CONTEXT.md`](../CONTEXT.md).

## Visão do semestre

| Fase | Semanas | Nome | Entregável |
|---|---|---|---|
| F0 | 1–2 | Ambientação e fundamentos | "Mapa zero" (limite municipal + setores sobre satélite) |
| F1 | 3–4 | Endereços (CNEFE) | Camada de endereços + tabela por espécie + decisão de recorte |
| F2 | 5–7 | Edificações | Camada municipal de edificações com `area_m2` + memória de comparação de fontes |
| F3 | 8–10 | Cruzamento e estatísticas | `atlas_pa.gpkg` + tabela mestra + fila de conferência |
| F4 | 11–13 | Mapa interativo | `mapa/index.html` navegável |
| F5 | 14–15 | Síntese e relatório | Banner + relatório + pacote reprodutível |
| F6 | 16 | Apresentação | Apresentação pública + retrospectiva |

## Equipe e papéis

| Papel | Qtde | Responsabilidade |
|---|---|---|
| Coordenação | 1 | Cronograma, atas, diário de bordo, interface com orientador(a) |
| Dados e downloads | 1–2 | Aquisição, organização de pastas, espelho/backup das bases no drive da equipe |
| SIG (QGIS) | 2 | Limpeza, recortes, junções espaciais, cartografia |
| Análise | 1–2 | Tabelas, estatísticas, validação amostral, comparação com o Censo |
| Comunicação | 1 | Mapa web, banner, texto final, apresentação |

Com 4 pessoas: fundir **Dados+Análise** e **SIG+Comunicação** em pares. Rodízio opcional na metade do semestre — as receitas garantem que qualquer um retome o passo do colega.

## Rituais

- **Reunião semanal de 1h** com pauta fixa: o que foi feito · o que está travado · o que vem a seguir.
- **Diário de bordo** por semana (modelo em [`DIARIO-MODELO.md`](./DIARIO-MODELO.md)) — vira o relatório final quase de graça.
- **Revisão de fase**: nenhuma fase "fecha" sem o critério de conclusão conferido pelo orientador(a).
- **Calendário reverso**: banner pronto **2 semanas antes** do evento de extensão; a folga da F5 é o buffer oficial do projeto.

---

## F0 — Ambientação e fundamentos (semanas 1–2)

- **Objetivo**: nivelar conceitos, ambiente pronto em todas as máquinas, papéis definidos.
- **Atividades**:
  1. Instalar **QGIS LTR** em todas as máquinas + plugins QuickMapServices, qgis2web e DataPlotly.
  2. Oficina interna de 2h: camadas, CRS (ler o glossário antes), formatos, o pipeline de 5 etapas.
  3. Criar a estrutura de pastas (`dados-brutos/`, `dados-processados/`, `mapa/`, `docs/`) e o drive compartilhado; definir papéis; decidir com o orientador a licença do material final (sugestão: CC BY 4.0) e onde o pacote será hospedado.
  4. Adicionar o basemap Esri World Imagery (QuickMapServices).
  5. Baixar a malha de setores (R03), filtrar o município e dissolver o limite (R10). Anotar o **bbox real**.
- **Receitas**: R03, R10.
- **Entregável**: **"mapa zero"** — limite municipal e setores sobre imagem de satélite.
- **Critério de conclusão**: todos os integrantes reproduziram o mapa zero na própria máquina.

## F1 — Endereços (semanas 3–4)

- **Objetivo**: base de endereços carregada, entendida e classificada; recorte territorial decidido.
- **Atividades**:
  1. Baixar o CNEFE do município (R01) e o dicionário (R02); **ler o dicionário em grupo**.
  2. Importar o CSV no QGIS (R09); mapa temático por espécie (domicílio × estabelecimento × em construção).
  3. Contar endereços por setor (R14 parcial).
  4. **Verificação decisiva**: abrir a malha de bairros da BA e filtrar `CD_MUN = 2924009` (R04).
     - **Se houver bairros** → adotá-los como recorte oficial do Atlas.
     - **Se não houver** → **plano B**: estatísticas por setor censitário (agrupados quando fizer sentido) + camada de rótulos com os nomes de bairros de conhecimento local, sempre com a ressalva "delimitação não oficial".
- **Receitas**: R01, R02, R04, R09, R14.
- **Entregável**: camada `enderecos_cnefe` + tabela "endereços por espécie" + **decisão de recorte registrada no diário**.
- **Critério de conclusão**: total de endereços do município documentado; mapa por espécie apresentado na reunião semanal.

## F2 — Edificações (semanas 5–7)

- **Objetivo**: camada municipal de edificações limpa, com área calculada e fonte primária escolhida com justificativa.
- **Atividades**:
  1. Baixar Overture buildings pelo bbox real (R06) e corrigir a codificação (R08).
  2. Baixar Google Open Buildings v3 (R07); quem estiver na trilha com código filtra via DuckDB (R15).
  3. **Comparação formal das duas fontes em 2 bairros-teste**: contagem, sobreposição visual sobre o satélite, casos em que uma vê e a outra não. Uma página de memória.
  4. Escolher a **fonte primária** (a outra vira conferência) — decisão registrada.
  5. Recortar pelo limite municipal (R11), remover polígonos-ruído (< 10 m²), calcular `area_m2` (R12), gerar o histograma (R16).
- **Receitas**: R06, R07, R08, R11, R12, R15 (opcional), R16.
- **Entregável**: camada `edificacoes` com `area_m2` + memória de comparação de fontes + histograma.
- **Critério de conclusão**: contagem municipal fechada; mediana de área plausível (referência do piloto: ~112 m²); decisão de fonte assinada pela equipe no diário.

## F3 — Cruzamento e estatísticas territoriais (semanas 8–10)

- **Objetivo**: associar endereços a edificações, medir a confiança de cada polígono e produzir a tabela mestra do Atlas.
- **Atividades**:
  1. Junção espacial pelo vizinho mais próximo (R13), raio inicial 25 m; testar 50 m; **documentar o raio escolhido**. Meta: ≥ 85% de associação (piloto: 93%).
  2. Investigar os não-associados: onde estão (zona rural? condomínios novos? dado defasado?) — isso É resultado, não falha.
  3. **Campos de confiança** (R21, R22): concordância entre as duas fontes, `confianca_fonte`, `nivel_verificacao` e `prioridade_campo`; exportar a **fila de conferência** (`fila_conferencia.csv`).
  4. Tabela mestra por recorte (R14): nº de edificações, área somada, mediana, edificações/km², endereços por edificação, % de endereços "em construção".
  5. Conferir contra o Censo (R05): endereços CNEFE × domicílios oficiais por setor — divergências grandes viram nota metodológica.
  6. **Auditoria visual amostral**: 30 edificações sorteadas por recorte analisado, conferidas contra o satélite; taxa de acerto registrada e `nivel_verificacao` atualizado para `conferido_tela`.
  7. Se houver ida a campo (opcional): começar pelo topo da fila — foto + `pavimentos_observados`, `nivel_verificacao` = `conferido_campo`.
- **Receitas**: R05, R13, R14, R21, R22.
- **Entregável**: **`atlas_pa.gpkg`** consolidado (todas as camadas padronizadas) + tabela mestra em CSV + fila de conferência.
- **Critério de conclusão**: auditoria amostral documentada; taxa de associação reportada com o raio utilizado; campos de confiança preenchidos em 100% das edificações.

## F4 — Mapa interativo (semanas 11–13)

- **Objetivo**: publicar o Atlas navegável.
- **Atividades**:
  1. Desenhar a simbologia: coropleta de edificações/km² por recorte; edificações coloridas por faixa de `area_m2`; endereços clusterizados.
  2. Simplificar para a web (R19).
  3. Exportar com qgis2web (R17) — ou folium (R18) na trilha com código.
  4. Rodapé com a linha de atribuição (R20).
  5. **Teste de usabilidade com 3 pessoas de fora da equipe** — anotar onde travam.
- **Receitas**: R17, R18, R19, R20.
- **Entregável**: **`mapa/index.html`** abrindo offline em navegador comum.
- **Critério de conclusão**: mapa abre em máquina "limpa", com legenda, camadas ligáveis e atribuições corretas; tamanho < 60 MB (meta < 25 MB).

## F5 — Síntese, honestidade metodológica e relatório (semanas 14–15)

- **Objetivo**: números finais com limitações explícitas; material de divulgação pronto.
- **Atividades**:
  1. Redigir a seção **"o que estes números NÃO dizem"**: pegada ≠ área construída; footprint ≠ terreno; teto da detecção automática; retrato 2022 do CNEFE; heurística da associação; distribuição de `confianca_fonte` e taxa de concordância entre fontes reportadas.
  2. Banner/slides no padrão da instituição.
  3. Consolidar o diário em relatório de extensão.
  4. Empacotar: `atlas_pa.gpkg` + CSVs + mapa + "como reproduzir" (lista das receitas usadas, na ordem).
- **Entregável**: relatório/banner + pacote de dados reprodutível.
- **Critério de conclusão**: revisão do orientador(a) aprovada; toda estatística publicada tem fonte, método e limitação.

## F6 — Apresentação e encerramento (semana 16)

- **Objetivo**: apresentação pública e fechamento.
- **Atividades**: apresentação de ~15 min com o mapa ao vivo; retrospectiva da equipe (o que manter/mudar numa próxima edição); publicação do pacote no repositório/drive institucional.
- **Entregável**: apresentação realizada + pacote final publicado.
- **Critério de conclusão**: material entregue à instituição; retrospectiva no diário.

---

## Planos B e entregável mínimo viável

| Se falhar… | Sinal | Plano B |
|---|---|---|
| Bairros IBGE não cobrem o município | Filtro da R04 retorna vazio | Recorte por setores + rótulos locais com ressalva (decisão da F1) |
| FTP do IBGE instável | Timeout nos downloads | Baixar tudo nas 2 primeiras fases e espelhar no drive da equipe |
| CSV do Google v3 grande demais | Máquinas travam | Trilha DuckDB (R15), laboratório da instituição, ou GeoParquet do source.coop |
| Fontes de edificações divergem muito | Contagens muito diferentes nos bairros-teste | A comparação formal da F2 decide; a divergência vira achado do relatório |
| Mapa web pesado | > 60 MB ou navegador trava | R19 agressiva: centroides em zoom baixo, menos casas decimais, camadas sob demanda |
| Semestre encurtar (provas, feriados) | Atraso ≥ 2 semanas | **Entregável mínimo viável**: fechar F3 + mapa simples (R18 com 1 camada) + relatório enxuto — o projeto ainda "fecha" decente |
| Evasão de integrantes | Papel descoberto | Papéis com backup + receitas autossuficientes: qualquer um retoma o passo do colega |

## Cuidados permanentes (valem em todas as fases)

- **Fontes proibidas**: Google Maps/Street View como fonte de dados; DNE dos Correios (pago — CEP já vem no CNEFE); Mapillary (share-alike viral). Ver [`FONTES.md`](./FONTES.md).
- **Privacidade**: nenhum dado pessoal; fotos de campo sem rostos e sem placas.
- **Método**: mediana em vez de média; todo número com fonte + método + limitação; decisões no diário.
