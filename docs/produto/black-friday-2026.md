# Black Friday 2026 (11.11 até a Cyber Monday)

Status: spec para o `frontend-developer`. Escrita em 2026-11-04.

## Problema e usuário
Em novembro, quem chega ao site já vem procurando "Black Friday de livros" e desconfia de preço inflado na véspera (a "Black Fraude"). Queremos que essa pessoa veja logo os descontos grandes de verdade e clique para a loja. O histórico de 90 dias, que é o nosso diferencial, é o argumento. A mudança é visual e temporária: uma faixa, um destaque nos descontos grandes e uma página `/black-friday/`, tudo com dados que o build já tem.

A referência (ofertasdiscos.com, checado em 2026-11-04) não tem tema sazonal, então não há o que copiar. Seguimos a `docs/marca/spec-visual.md` sem trocar paleta, logo nem fontes.

## Escopo do MVP
1. **Liga e desliga por data, no build.** Uma constante em `build.py`:
   `CAMPANHA = (date(2026, 11, 5), date(2026, 12, 1))  # inclusive, em BRT`.
   Fica ativa quando `now.astimezone(BRT).date()` está dentro do intervalo. O `now` é o mesmo do `build()`: o relógio real no deploy e o último `checked_at` no `--dev`. Como o pipeline faz deploy a cada 30 min, a campanha entra e sai sozinha, sem PR novo. Não há variável de ambiente nem flag extra.
2. **Faixa sazonal**, uma linha logo abaixo do header, em todas as páginas e só durante a campanha:
   - texto: "**11.11 e Black Friday:** descontos comparados com o nosso histórico de preço. *Ver os maiores*". O texto inteiro é um link para `/black-friday/`;
   - fundo `--wine` (marinho) e texto `--ivory` nos dois temas; o "Ver os maiores" em `--rose`. Altura de cerca de 36px, 14px/600, centralizada. Não é sticky: o header continua sendo o único elemento fixo;
   - no celular cabe em uma linha até 360px. Abaixo disso, encurtar para "Black Friday: *ver os maiores descontos*" (dois `<span>`, um deles escondido por media query);
   - não tem botão de fechar, contagem regressiva, "termina em", "últimas horas" nem estoque.
3. **Destaque de desconto grande.** Durante a campanha, o sticker do card (`.sticker`) e a pílula do hero e da página do livro (`.off-pill`) ganham a classe `--forte` quando `off(o) >= 30`. O visual é invertido: `background: var(--text); color: var(--bg)`, que fica marinho sobre claro no tema claro e claro sobre marinho no escuro, sem cor nova. Mesmo tamanho e mesma rotação do sticker atual. Fora da campanha, nada muda.
   - Limiar: `BF_MIN = 30` em `build.py`.
4. **Página `/black-friday/`**, gerada em `render_pages` quando a campanha está ativa:
   - entra o livro com `o["oferta"]`, `not o["velho"]` e (`off(o) >= BF_MIN` ou `seal(o) == "90d"`). A ordem é a do `ranked()`: selo de 90 dias primeiro, depois o maior desconto;
   - reaproveita o `all_page`/`feed(..., full=True)`: mesmo grid, ordenação por JS e "carregar mais". Sem os blocos intercalados se der trabalho; eles são opcionais aqui;
   - H1 "Black Friday de livros". Lede: "Ofertas ativas com 30% ou mais de desconto ou no menor preço que vimos em 90 dias. Cada livro mostra quando conferimos o preço; o preço final é o da loja.";
   - se ninguém se qualificar: `<p class="vazio vazio--fixo">` com "Nenhum livro com desconto grande agora. Veja todas as <a href="/ofertas/">ofertas ativas</a>." A página continua existindo, e a faixa continua apontando para ela;
   - adicionar `"black-friday"` ao `RESERVED`;
   - no rodapé, coluna "Ofertas", um link "Black Friday" só durante a campanha.
5. **Depois de 01/12**, a página continua sendo gerada, mas só com o H1 "A Black Friday 2026 acabou" e um link para `/ofertas/`, para não quebrar os links já compartilhados. Não usar `_redirects` (seria PR sensível). A faixa, o `--forte` e o link do rodapé somem.

## Fora do MVP
- **Post especial nos canais e no bot** (`alerts-engineer`). Vale fazer se a página der clique na primeira semana. É PR separado.
- **Seção Black Friday na home**: repetiria livros que já estão no hero e nos destaques e quebraria a regra de "nenhum livro em mais de 2 lugares". A faixa já cobre.
- **Filtro "Black Friday" no `app.js`.** A página estática já resolve sem JS. Faz sentido só se o Elias quiser o filtro dentro de `/ofertas/`.
- **Tema "black" (fundo preto, dourado etc.)**: sai da marca.
- **Exigir histórico próprio para entrar na página**, isto é, não aceitar só o "de/por" da loja. Ver a decisão 3.

## Fluxo do usuário
1. A pessoa abre qualquer página entre 05/11 e 01/12 e vê a faixa marinha abaixo do header.
2. Rolando a home, os cards com 30% ou mais aparecem com o sticker invertido, que se destaca dos stickers coloridos.
3. Ela toca na faixa e cai em `/black-friday/`: só descontos grandes ou no menor preço em 90 dias, com o horário da verificação em cada card.
4. Ela toca no card ou no botão e segue para `/r/<id>`, que leva à loja. O fluxo de afiliado é o atual.

## Critérios de aceite
- [ ] Com `now` em 04/11 e em 02/12 (BRT), o HTML não tem a faixa, `--forte` nem o link do rodapé, e `/black-friday/` não existe em 04/11. Em 02/12 a página existe só com a mensagem de encerramento. Com `now` em 05/11 e em 01/12, tudo aparece. Teste no `selftest()` com o `now` fixo.
- [ ] Um livro com `off = 30` ganha `sticker--forte` e um com `off = 29` não. Sem oferta (`off(o) == 0`), não há sticker.
- [ ] `/black-friday/` não lista livro sem oferta, `velho` ou com desconto abaixo de 30% sem o selo de 90 dias. Teste no `selftest()`.
- [ ] Todo card da página mostra a loja, o "visto … às HHhMM" e o rodapé com o aviso de associado e o "preço final é o da loja", como nas outras páginas (reuso de `card()`/`foot()`).
- [ ] Nenhum texto novo menciona posição, ranking, "mais vendido", contagem regressiva, prazo ou estoque.
- [ ] Sem JS (desligado no navegador), a faixa, a página e o destaque funcionam. O JS só acrescenta a ordenação na página, que já existe.
- [ ] `_headers`, `_redirects`, `wrangler.jsonc` e workflows ficam intocados. O diff fica em `build.py` e `static/style.css`, com no máximo uma linha no `app.js` se precisar.
- [ ] **Contraste AA**, conferido com `docs/marca/contraste.py` ou outra calculadora, nos dois temas (`prefers-color-scheme` e `data-theme`):
  - `--ivory` sobre `--wine` e `--rose` sobre `--wine` ≥ 4,5:1 (a faixa é texto de 14px);
  - sticker `--forte`: `--bg` sobre `--text` ≥ 4,5:1, e a borda do sticker contra o fundo do card ≥ 3:1. No escuro, se o marinho da faixa se confundir com o `--bg`, adicionar uma borda inferior de 1px em `--line`.
- [ ] O sticker `--forte` não depende só de cor: o `<span class="sr">, 30% de desconto</span>` que já existe continua lá.
- [ ] A faixa tem foco visível (o mesmo `:focus-visible` dos links) e o "Pular para o conteúdo" continua sendo o primeiro foco da página.
- [ ] **Mobile**: em 360px e 320px, a faixa fica em uma linha sem rolagem horizontal, a área de toque do link tem pelo menos 44px de altura e o header sticky não cobre a faixa ao carregar a página. Lighthouse mobile da home sem regressão de CLS: a faixa vem no HTML, sem nada inserido por JS.
- [ ] `prefers-reduced-motion`: nenhuma animação nova.

## Divisão por agent (ordem)
1. **frontend-developer**: tudo do escopo (`build.py`: `CAMPANHA`, `BF_MIN`, faixa no `shell()`, `--forte` em `card()`/`slide()`/`book_page()`, página e rodapé, `RESERVED`, testes no `selftest()`; `static/style.css`: `.sazonal`, `.sticker--forte`, `.off-pill--forte`). Abre o PR no branch `Elias-arruda/black-friday-2026`.
2. **collector-engineer**: nada.
3. **alerts-engineer**: nada no MVP. O post especial é PR futuro.
4. **security-auditor**: confere que o texto novo é constante (sem dado externo sem escape), que `_headers`/`_redirects` não mudaram e que os links novos são internos.
5. **code-reviewer**: revisa com o web-design-guidelines (contraste, foco, mobile). Depois vem o review do Codex pelo fluxo normal. **O PR não é sensível** se ficar só em `build.py` e `style.css` sem tocar em texto legal, `/r/` ou headers. Se mexer no aviso do rodapé, passa a ser sensível.

## Riscos
- **CDC e publicidade enganosa.** "Black Friday" com desconto inflado é o risco clássico. O desconto mostrado é o "de/por" da loja quando o livro tem menos de 30 dias de histórico. Por isso a lede não promete "desconto verificado pelo histórico" e diz "comparados com o nosso histórico" só na faixa, que fala do site como um todo. O selo de 90 dias segue a regra atual (90 dias reais).
- **Regra 1 (Amazon):** nada muda. A página usa o `offers.json` que já existe e não faz request novo.
- **Curadoria, não despejo:** a página é um subconjunto das ofertas ativas, não uma lista nova.
- **LGPD:** não há dado de usuário.
- **Custo:** zero. São páginas estáticas a mais no mesmo Worker Free.
- **Esquecer a campanha ligada:** não acontece, porque o fim é uma data no código e o build roda a cada 30 min.

## Decisões em aberto para o Elias
1. **Janela:** 05/11 a 01/12 (Cyber Monday é 30/11). O 11.11 já começou. Quer ligar no dia do merge, com início em 04/11?
2. **Limiar do destaque:** 30%? Com 25% entram mais livros; com 40%, menos e mais fortes.
3. **Critério da página:** aceitar o "de/por" da loja (proposta) ou exigir histórico nosso de 30 dias ou mais, isto é, só o que passou pela mediana ou pelo selo? A segunda opção é mais à prova de "Black Fraude", mas a página pode ficar quase vazia, porque muitos livros entraram no catálogo em 20/10.
4. **Nome:** "11.11 e Black Friday" na faixa e "Black Friday" na página, ou só "Black Friday" em tudo?
