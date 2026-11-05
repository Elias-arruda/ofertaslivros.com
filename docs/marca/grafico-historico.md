# Gráfico do histórico de preço (direção visual, 2026-11-04)

Proposta para o Elias validar. Implementação: `frontend-developer`. Tokens reais do `static/style.css` (a §2 da spec ainda lista o vinho antigo). Base visual: post 02 do kit de redes (linha marinho, tracejado vermelho no menor preço, ponto vermelho no preço atual, frase embaixo).

## 1. Onde entra (decisão do Elias, 2026-11-04: opção B)
- **Página `/livro/<id>/`:** versão completa, abaixo do `.meta`, no lugar do sparkline antigo, em `<figure id="historico">`.
- **Card:** continua como era, com o selo "Menor preço desde X". Logo abaixo do selo entra um link discreto, "ver histórico". Sem JS ele leva a `/livro/<id>/#historico`; com JS abre o modal. O link só aparece quando o livro tem gráfico de verdade, ou seja, `price_points` com ao menos um dia antes de hoje. Nada de link para gráfico vazio.
- **Modal:** ao abrir (pelo link ou pelo clique normal no card), o `app.js` busca a página do livro e importa o `#historico` pronto, com `DOMParser` e `importNode`, sem HTML de string no DOM. Até carregar, ou sem JS, fica a frase curta e o link "Página do livro".
- **Avaliadas e descartadas:** (A) o gráfico só no modal, sem o link, que deixava o histórico escondido; (C) um mini-gráfico sempre visível no card, que sem escala desenha igual uma queda de 2% e uma de 40%.

## 2. Cores e como distinguir as lojas
O gráfico fica num painel neutro (`.hc`: fundo `--bg2`, borda 1px `--line`, raio 18px, padding 14px; 12px no celular), para não herdar o tingido da categoria do `.livro`. Contraste medido contra `--bg2` (claro #f3f6f9 / escuro #18233b).

| Papel | Token | Claro | Escuro | Traço |
|---|---|---|---|---|
| Linha Amazon | `--hc-amz: var(--text)` | #1c2b4a, 12,96:1 | #e6ebf3, 13,07:1 | 2.5, com marcador r=3 em cada leitura |
| Linha Mercado Livre | `--hc-ml` (novo) | #0f7a75, 4,77:1 | #5fd3cc, 8,70:1 | 2, sem marcador |
| Menor preço (tracejado e rótulo) | `--coral` | #b3262f, 5,98:1 | #ff8a8f, 6,92:1 | 1.5, `stroke-dasharray="4 4"` |
| Maior preço, datas | `--muted` | #4a5670, 6,78:1 | #a9b4c8, 7,49:1 | texto |
| Linha-guia do maior preço | `--line` | | | 1, decorativa |

Sem depender de cor: (a) **rótulo direto** com o nome da loja na ponta de cada linha, na cor dela (nada de legenda); (b) **marcadores só na Amazon**, que ainda mostram onde houve leitura de fato; (c) espessuras diferentes. Não usar o laranja da Amazon nem o amarelo do ML. Só uma loja: uma linha `--hc-amz`, mesmo se for o ML, e o rótulo continua.

## 3. Elementos
- **Eixo x:** datas reais, de `max(primeiro ponto de qualquer loja, hoje − 89)` até hoje. Domínio mínimo de 7 dias: com 3 dias, a linha ocupa só a ponta direita, o que mostra que o histórico é novo.
- **Eixo y:** do menor ao maior preço das séries mostradas, com 10% de folga. Sem grade e sem ticks. Só dois rótulos à esquerda, 13 u: o maior (`--muted`, sobre a linha-guia `--line`) e "menor R$ 34,90" (`--coral`, logo acima do tracejado). Se o maior for igual ao menor, só o tracejado.
- **Tracejado:** o menor preço entre **todas** as séries mostradas, o mesmo universo do `seal_of()`, que exige o mínimo de todas as lojas elegíveis.
- **Ponto atual:** na ponta da loja vencedora, r=5, preenchido `--coral` com contorno 2px `--bg2`. Datas embaixo: a primeira à esquerda ("18/10") e "hoje" à direita.
- **Frase-resumo** (`figcaption`, 15px/600 `--text`), sempre derivada do `seal(o)` e nunca do desenho, para não contradizer o selo:
  - `90d`: "Hoje é o menor preço dos últimos 90 dias."
  - `since`: "Hoje é o menor preço desde DD/MM." (o mesmo `o["since"]` do selo)
  - `None`: o `chart_label()` atual, "desde 18/10: R$ 34,90 a R$ 59,90", sem a palavra "menor".

## 4. Estados
- **Nenhuma loja com 2 dias distintos:** sem SVG. Só `<p class="hist">Primeira leitura em DD/MM: R$ X.</p>`.
- **Menos de 7 dias:** desenha, com o domínio mínimo de 7 dias.
- **Buraco na Amazon:** reta entre leituras, com o marcador mostrando o que é leitura real. Buraco de mais de 7 dias quebra a linha (novo `M` no path), sem inventar preço.
- **Amazon vencida (`velho`):** a linha para na última leitura (não vai até hoje), e o rótulo fica "Amazon, 28/10" em `--muted`. Se ela for a vencedora, o ponto atual fica vazado (preenchido `--bg2`, contorno 2px `--coral`). O aviso "Preço pode estar desatualizado" continua no `.meta`.
- **Rótulos de ponta colidindo:** ordenar por y e garantir 16 u entre eles.

## 5. Dimensões
`viewBox="0 0 300 150"`, `width="100%"`, CSS `.hc svg { display:block; max-width: 420px; height:auto }`. No celular de 360px (cerca de 290px úteis) a escala é ~1:1, e o texto de 13 u fica com 12–13px. No desktop, até 1,4x. Área do gráfico: x 4–204, y 22–124. Coluna de rótulos das lojas: x ≥ 210, `text-anchor="start"`. Datas em y 142. Fonte: `font: 600 13px var(--sans)` via classe CSS, com `font-variant-numeric: tabular-nums`. Sem atributo `style=` (CSP); cores só por classe (`.hc-amz`, `.hc-ml`, `.hc-min`, `.hc-now`, `.hc-now--velho`, `.hc-lbl`).

```
Desktop (coluna direita do .livro, SVG até 420px)          Celular (~290px úteis, empilhado)
+--------------------------------------------------+       +------------------------------+
| R$ 59,90 ----------------------                  |       | R$ 59,90 ---------           |
|    o--o   \__      o          Amazon, 28/10      |       |  o--o \_   o   Amazon, 28/10 |
|  ___/  \_    \____/                              |       |  _/  \_ \__/                 |
|          \__________________@ Mercado Livre     |       |     \__________@ Mercado Liv.|
| menor R$ 34,90 - - - - - - - - - - - -           |       | menor R$ 34,90 - - - - -     |
| 18/10                          hoje              |       | 18/10              hoje      |
+--------------------------------------------------+       +------------------------------+
 Hoje é o menor preço desde 18/10.                           Hoje é o menor preço desde 18/10.
 > Ver preços por dia                                        > Ver preços por dia
```
(`@` = ponto atual da vencedora; `o` = leituras da Amazon.) No celular, se "Mercado Livre" não couber na coluna de 88 u, reduzir a área do gráfico, nunca abreviar o nome.

## 6. Acessibilidade e markup
```html
<figure class="hc">
  <svg viewBox="0 0 300 150" role="img" aria-labelledby="hc-t" focusable="false">
    <title id="hc-t">Preço desde 18/10. Amazon: menor R$ 36,90, maior R$ 59,90, último R$ 39,90 em 28/10.
      Mercado Livre: menor R$ 34,90, maior R$ 49,90, hoje R$ 34,90.</title>
    …paths, circles, text…
  </svg>
  <figcaption>Hoje é o menor preço desde 18/10.</figcaption>
  <details class="hc-tab"><summary>Ver preços por dia</summary>
    <table><caption class="sr">Menor preço do dia, por loja</caption>
      <thead><tr><th scope="col">Dia</th><th scope="col">Amazon</th><th scope="col">Mercado Livre</th></tr></thead>
      <tbody><tr><th scope="row">04/11</th><td>—</td><td>R$ 34,90</td></tr>…</tbody></table>
  </details>
</figure>
```
- Tabela do dia mais novo para o mais velho, só com os dias que têm leitura, e `—` onde a loja não tem (o leitor de tela lê o `—` como traço; usar `<span class="sr">sem leitura</span>`). Uma coluna por loja presente.
- `summary` com área de toque mínima de 44px e o foco padrão do site. Os `<text>` do SVG ficam visíveis, mas o leitor de tela lê o `<title>`.
- Valores com `brl()`, que já é escapado. `id` do title único se houver mais de um gráfico na página.
- Tooltip em JS: fica de fora; a tabela cobre o caso. Entra se o Elias pedir.
