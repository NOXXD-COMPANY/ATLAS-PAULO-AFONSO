# ATLAS URBANO DE PAULO AFONSO — DOCUMENTAÇÃO DO PROJETO

---

## IDEIA INICIAL

O **Atlas Urbano de Paulo Afonso** nasceu da percepção de que o Brasil produziu, nos últimos anos, um conjunto inédito de dados territoriais abertos — endereços georreferenciados do Censo 2022, malhas territoriais detalhadas e bases globais de edificações extraídas por satélite e aprendizado de máquina. Porém, quase nenhuma cidade média brasileira tem esse material **combinado, verificado e apresentado** de forma útil à população e aos gestores.

O projeto propõe construir, **em um semestre letivo e a custo zero**, o primeiro retrato aberto e reprodutível do território construído de Paulo Afonso/BA: quantas edificações existem, de que tamanho são, onde estão, quantos endereços há e de que tipo, e como tudo isso se distribui pelos bairros.

**O resultado é público:** um mapa interativo, tabelas de estatísticas territoriais e uma memória metodológica que permite a qualquer pessoa refazer — e atualizar — o trabalho futuramente.

### Objetivo Geral
Construir e publicar o inventário aberto de edificações e endereços de Paulo Afonso/BA, com estatísticas por recorte territorial e mapa interativo, usando exclusivamente dados públicos e ferramentas gratuitas.

### Objetivos Específicos
1. Inventário municipal de **edificações** com área de pegada de telhado calculada para 100% da área urbana.
2. Base de **endereços** do CNEFE classificada por espécie, com contagem fechada para o município.
3. **Tabela mestra por bairro/setor**: nº de edificações, área somada e mediana de telhado, edificações/km², endereços por edificação, % de endereços "em construção".
4. **Mapa interativo** navegável em qualquer navegador + **memória metodológica** reprodutível (receitas + diário).
5. **Campos de confiança** em 100% das edificações e fila de conferência de campo priorizada.

### Perguntas que o Atlas responde
1. Quantas edificações existem em Paulo Afonso, e onde?
2. De que tamanho são (pegada de telhado), e como os tamanhos se distribuem?
3. Quantos endereços existem, e de que espécie (domicílios, estabelecimentos, em construção)?
4. Como cada bairro se compara — densidade construída, tamanho típico, endereços por edificação?
5. O que os dados abertos não enxergam — e com que confiança se pode afirmar cada número?

---

## PÚBLICO-ALVO

O Atlas Urbano de Paulo Afonso é destinado a múltiplos públicos:

- **Gestores e servidores municipais**: secretarias de planejamento urbano, obras, habitação e tributação que necessitam de um retrato territorial atualizado da cidade para embasar decisões.
- **Pesquisadores e acadêmicos**: que estudam urbanismo, geografia, geoprocessamento e desenvolvimento regional, podendo usar o Atlas como base para pesquisas e comparações.
- **Estudantes universitários**: em especial da área de geociências, engenharia, arquitetura e urbanismo, que podem aprender com a metodologia aberta e reprodutível do projeto.
- **Jornalistas e comunicadores**: que desejam produzir matérias baseadas em dados sobre a cidade, como crescimento urbano, distribuição de moradias e perfil dos bairros.
- **Cidadãos em geral**: moradores de Paulo Afonso que queiram entender melhor a sua cidade por meio de um mapa público e acessível.
- **Organizações da sociedade civil**: ONGs, associações de bairro e movimentos sociais interessados em dados territoriais para advocacy e projetos comunitários.

---

## PROBLEMAS QUE O PROJETO SOLUCIONA

1. **Ausência de retrato territorial aberto**: Paulo Afonso, como a grande maioria das cidades médias brasileiras, não possui um inventário público, atualizado e acessível de suas edificações e endereços. O Atlas preenche essa lacuna.

2. **Dados existem, mas estão dispersos e não processados**: O Brasil possui fontes de dados abertas de alta qualidade (CNEFE/IBGE, Overture Maps, Google Open Buildings), mas essas informações nunca foram combinadas, conferidas e apresentadas de forma útil para Paulo Afonso.

3. **Planejamento urbano sem base territorial confiável**: Decisões sobre infraestrutura, saneamento, transporte e habitação ficam comprometidas quando não se sabe com precisão onde e quantas edificações existem na cidade.

4. **Barreira de acesso a ferramentas e metodologia**: Geoprocessamento é percebido como caro ou complexo. O projeto demonstra que é possível produzir análises territoriais sofisticadas com custo zero, usando QGIS e dados públicos.

5. **Falta de formação prática em geoprocessamento**: Estudantes universitários raramente têm oportunidade de trabalhar com dados reais em projetos com impacto social concreto. O Atlas resolve isso ao ser um projeto de extensão com produto final real.

6. **Impossibilidade de reprodução e atualização**: Mesmo quando existem análises territoriais, elas raramente são acompanhadas de metodologia clara. O Atlas entrega receitas documentadas que permitem que qualquer pessoa refaça e atualize o trabalho.

7. **Desconhecimento sobre o que os dados públicos não enxergam**: O projeto também educa sobre as limitações dos dados — pegada de telhado ≠ área construída; footprint ≠ limite de terreno — contribuindo para uso mais responsável das informações territoriais.

---

## EQUIPE

| Nome | Função | Responsabilidades Principais |
|---|---|---|
| **Caio Lúcio** | Coordenador | Cronograma, atas de reunião, diário de bordo, interface com orientador(a), organização geral do projeto |
| **Arthur Henrique** | Dados e Downloads | Aquisição das bases de dados, organização de pastas, espelhamento/backup no drive da equipe |
| **Luís Gustavo** | Análise | Tabelas, estatísticas, validação amostral, comparação com o Censo |
| **João Vitor** | SIG (QGIS) | Limpeza de dados, recortes territoriais, junções espaciais, cartografia |
| **Rafael Santos** | SIG (QGIS) | Limpeza de dados, recortes territoriais, junções espaciais, cartografia |
| **Elliton Luis** | Comunicação | Mapa web, banner, texto final, apresentação pública |

---

## MAPA DE SEMANAS (FASES DO PROJETO)

| Fase | Semanas | Nome | Entregável |
|---|---|---|---|
| **F0** | 1–2 | Ambientação e fundamentos | "Mapa zero" (limite municipal + setores sobre satélite) |
| **F1** | 3–4 | Endereços (CNEFE) | Camada de endereços + tabela por espécie + decisão de recorte |
| **F2** | 5–7 | Edificações | Camada municipal de edificações com `area_m2` + memória de comparação de fontes |
| **F3** | 8–10 | Cruzamento e estatísticas | `atlas_pa.gpkg` + tabela mestra + fila de conferência |
| **F4** | 11–13 | Mapa interativo | `mapa/index.html` navegável |
| **F5** | 14–15 | Síntese e relatório | Banner + relatório + pacote reprodutível |
| **F6** | 16 | Apresentação | Apresentação pública + retrospectiva |

---

## INFORMAÇÕES DO MUNICÍPIO

| Campo | Valor |
|---|---|
| Cidade-alvo | Paulo Afonso/BA |
| Código IBGE | 2924009 |
| População | 112.870 habitantes (Censo 2022) |
| Custo do projeto | R$ 0,00 |
| Edificações esperadas | 30.000–60.000 (a confirmar na F2) |

---

*Última atualização: 2026-08-15 | Coordenador: Caio Lúcio*
