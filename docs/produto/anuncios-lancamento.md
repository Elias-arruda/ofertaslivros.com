# Spec: anúncios pagos de lançamento

Status: spec do `product-manager`, escrita em 2026-11-07 a pedido do Elias ("quero começar a anunciar, da melhor forma possível, bem otimizado e acertado"). Revisada no mesmo dia com duas decisões do Elias: o destino é o site (uma cópia da vitrine com a tag `ads`) e o canal é só o Instagram. Nada implementado. Base conferida na `origin/main` em 13caff0 (2026-11-07).

## 1. Problema e usuário

**Em uma frase:** um leitor brasileiro que compra livro pela internet e nunca ouviu falar do site vê um anúncio no Instagram. Ele cai na nossa vitrine, que é a mesma da home, com preço conferido e histórico de 90 dias, e clica numa oferta. A compra sai com a tag `ofertaslivrads-20`, que separa no relatório da Amazon a venda vinda do anúncio. O canal do Telegram aparece num banner secundário, para quem não comprar agora voltar depois.

**Por que vender rápido:** a conta da seção 3 mostra que a comissão de livro não paga o clique. O valor estratégico é liberar a Creators API, que pede cerca de 10 vendas qualificadas em 30 dias. Segundo fonte secundária, esse ritmo precisa ser **mantido** para não perder o acesso. A meta do teste é justamente essa: cerca de 10 vendas com a tag `ads` em 14 dias, a um custo conhecido.

## 2. O que as regras dos programas permitem (o item crítico)

### 2.1 Amazon Associados BR

Fonte: [Políticas do Programa de Associados](https://associados.amazon.com.br/help/operating/policies), versão "Atualizado: 14 de abril de 2026", lida em 2026-11-07.

| Pergunta | Resposta | Cláusula |
|---|---|---|
| Anúncio pago com o link de afiliado (ou o nosso `/r/`) direto no destino | **Não.** A compra que vem de link exibido em "Ferramenta de Busca", definição que inclui "serviço de publicidade patrocinada", é desqualificada. O `/r/` direto também conta como "Link de Redirecionamento": manda para a Amazon "sem exigir que o cliente clique em um link ou execute alguma outra ação afirmativa nesse site intermediário" | Regulamento de Comissões 2(d) e 2(e) |
| Link com a tag fora do nosso Site, como no texto do anúncio | **Não.** Não criar links "formatados com sua tag de Associado" para "divulgar em um site que não seja o seu Site" | Requisitos 6(b) |
| Anúncio pago que leva para o nosso site | **Sim.** "Você poderá adquirir anúncios patrocinados em resultado de busca", desde que direcionem "ao seu site", e não via Link de Redirecionamento. Para anúncio em rede social não há cláusula específica, mas a mesma lógica (anúncio → nossa página → clique do usuário) atende a 2(d), 2(e) e 6(b) | Requisitos 6(f) |
| Lance em palavra-chave com "amazon", "kindle", outras marcas ou erros de grafia | **Não.** É "Inserção Proibida de Pesquisa Paga": a compra é desqualificada e a conta fica em violação. Se a Amazon pedir, a marca tem que entrar como palavra-chave negativa | Regulamento 2(c); Requisitos 6(e) e 6(f) |
| Marca da Amazon no nome de conta, página ou grupo em rede social | **Não** | Requisitos 1(g) |
| Promover a Amazon em si (anúncio "ofertas da Amazon", logo) | **Não**, salvo o que o contrato permite expressamente. O anúncio promove o **nosso** site e canal, sem nome nem logo das lojas | Requisitos 4 e 6(l) |
| Encurtador ou formato de anúncio que esconde que o destino é a Amazon | **Não** | Requisitos 6(v) e 6(w) |
| Imagem de produto vinda da Amazon no criativo | **Não.** O Conteúdo do Programa só pode ser exibido "apenas em seu Site". Hoje o site não usa imagem da Amazon (`collector/capas.py`), e o criativo também não pode usar | Licença 1(a) e 2(h) |
| Preço no anúncio | Exige "carimbo de data/horário" junto e o aviso de que o preço pode mudar. **Decisão: o criativo não mostra preço.** O preço fica no site, que já cumpre isso | Licença 2(i) |

**Conclusão para a Amazon:** o anúncio sempre aponta para uma página do nosso site. O link de afiliado só aparece depois de um clique do usuário nessa página. Sem lance em marca, sem nome ou logo das lojas no criativo e sem preço no criativo.

**A conferir (Elias, 5 min):** no Associates Central, em "Seus sites e aplicativos", ver se o canal do Telegram e o Canal do WhatsApp estão cadastrados como Sites (Requisitos 1). Isso já vale hoje, mas o anúncio vai multiplicar o tráfego do canal.

### 2.2 Mercado Livre (Afiliados e Criadores)

**Não consegui ler o texto oficial.** A página do programa ([mercadolivre.com.br/l/afiliados-home](https://www.mercadolivre.com.br/l/afiliados-home)) e a central de ajuda respondem 403 para acesso automatizado, e os Termos ficam no portal, com login. Não forcei o acesso.

O que dizem as fontes secundárias (não oficiais, 2026), em resumo:
- é proibido comprar anúncio em buscador (Google Ads, Shopping, Bing) para link de afiliado e dar lance na marca "Mercado Livre";
- o encurtador pode fazer perder a comissão;
- a divulgação orgânica é permitida.

Fontes: [ecommercenapratica](https://ecommercenapratica.com/blog/afiliado-mercado-livre/), [hunterhub](https://hunterhub.com.br/blog/programa-de-afiliados-mercado-livre-como-funciona-comissao-afiliados-ml/), [divulganinja](https://www.divulganinja.com.br/blog/mercado-livre-afiliados-10-perguntas-frequentes-erros).

**Conclusão para o ML, conservadora:**
- nada de anúncio em buscador no MVP;
- anúncio em rede social para o nosso site, com o link do ML só depois do clique do usuário, como na Amazon;
- **o Elias abre os Termos no portal (logado) antes de ligar a campanha** e confirma se há cláusula contra tráfego pago para página própria. Se houver, a vitrine do anúncio mostra só ofertas da Amazon.

### 2.3 Regras das plataformas de anúncio

- **Meta:** a página de destino tem que funcionar, deixar a pessoa sair da página e corresponder ao que o anúncio promete ([non-functional landing page](https://transparency.meta.com/policies/ad-standards/product-format-specific-policies/non-functional-landing-page/), lido em 2026-11-07). Uma página só de links de afiliado tende a ser reprovada como baixa qualidade (fonte secundária). A vitrine tem conteúdo próprio: o histórico de preço, o horário da verificação e a curadoria.
- **Google Ads:** proíbe "destinos que servem exclusivamente para direcionar usuários a outro lugar" ([Requisitos de destino, "Conteúdo original insuficiente"](https://support.google.com/adspolicy/answer/6368661?hl=pt-BR), lido em 2026-11-07, sem data na página). Isso pesa contra o Google no MVP.

## 3. Canal e objetivo: a conta

### 3.1 Margem

| Premissa | Valor | Origem |
|---|---|---|
| Comissão média por venda | **R$ 3 a 5** | 1ª venda importada no `/painel` (05/11): R$ 3,77. A taxa de livros é de **5 a 10%** por fontes secundárias. O Elias confere a taxa real em Associates Central > Tabela de taxas (exige login) |
| Janela de atribuição | 24 h, com o carrinho todo contando | Amazon e ML, por fontes secundárias. A comissão pode vir de outros itens |
| CPC de link no Meta BR, nicho livros | R$ 0,25 a 0,70 | **Estimativa** de mercado, sem fonte oficial. O teste mede o real |

### 3.2 Anúncio → site → venda

- 1.000 cliques × 25% que clicam numa oferta × 5% que compram = cerca de 12 vendas.
- Com CPC de R$ 0,40, isso dá **CPA de cerca de R$ 32** contra uma comissão de R$ 4.
- O **CPC de equilíbrio** é comissão × taxa de conversão = 4 × 0,0125 = **R$ 0,05**. Não existe no Meta nem no Google.
- Essa via só faz sentido como "compra" das vendas da Creators API: perto de R$ 300 por 10 vendas, e todo mês de novo.

### 3.3 Anúncio → canal do Telegram

- Com 15 a 25% de entrada no canal a partir de uma landing própria do canal, o **custo por membro** fica em R$ 1,60 a 2,70, com CPC de R$ 0,40.
- O valor do membro ainda não é conhecido. Ele sai do teste:
  - receita do membro em 30 dias = comissão da tag `ofertaslivrtg-20` em 30 dias ÷ membros do canal;
  - equilíbrio: custo por membro ≤ receita mensal do membro × meses que ele fica.
- Com números ilustrativos (1.000 membros, 10 vendas por mês, R$ 4 cada), o membro rende R$ 0,04 por mês. Isso fica **abaixo** do custo por membro.

### 3.4 Leitura honesta da conta

Nenhuma das duas vias se paga só com a comissão de livro, pelo menos com estas premissas. O que justifica um teste **pequeno e com teto** é:
- liberar e manter a Creators API, que tira a dependência da exceção de navegador na regra 1, hoje com risco de banimento aceito;
- chegar à Black Friday (27/11) com uma base no canal.

O teste serve para trocar as estimativas por números reais. Se o custo por membro vier muito abaixo do estimado, a conta muda.

### 3.5 Recomendação: Meta, só Instagram, com destino na vitrine

**Decisão do Elias (2026-11-07):**
- campanha no Meta só com Instagram: Feed, Stories e Reels;
- posicionamentos manuais, com Facebook, Messenger e Audience Network desligados no começo;
- o anúncio leva para o site, numa cópia da vitrine com a tag `ads`.

**Objetivo:** Tráfego, com a meta de desempenho "Maximizar cliques no link", que não exige pixel. A conversão de verdade (clique de saída para a loja e venda) é medida do nosso lado (seção 5).

**Destino: `/vitrine/` (nome a confirmar, decisão 9).** É a mesma página da home, gerada pelo mesmo `page()` do `build.py`, com duas diferenças: `noindex`, e os links de compra apontam para `/r/<id>/ads`.

**Por que não `/ofertas/`:** essa página já existe. É a lista completa (`all_page`, com as faixas `/ofertas/40/` e `/ofertas/50/`), está no menu, é indexada e usa `/r/<id>`. Pôr `noindex` e a tag `ads` nela mudaria o SEO e misturaria a venda orgânica com a do anúncio. Por isso a recomendação é um caminho novo. Se o Elias quiser mesmo `/ofertas/`, a página perde o tráfego orgânico e a separação das vendas deixa de ser limpa.

Por que Instagram:
- leitor de livro está lá (bookstagram), e capa e vitrine funcionam no visual;
- não há lance em palavra-chave, então o risco da marca (Amazon 2(c), 6(e), 6(f)) e a dúvida do ML sobre buscador nem aparecem;
- com posicionamentos manuais, o teste mede um público só, sem o clique acidental da Audience Network.

Alternativas avaliadas:

| Canal | Por que não agora | Quando vale |
|---|---|---|
| Facebook Feed e Audience Network | Ficaram de fora por decisão do Elias. A Audience Network costuma trazer clique acidental e barato | Facebook Feed como 2º conjunto, se o Instagram der custo por clique de saída bom |
| Google Search | Tem a melhor intenção de compra, mas: o ML pode proibir buscador; a página corre o risco de "conteúdo original insuficiente"; o volume de termos genéricos sem marca é baixo; e otimizar para conversão exige tag | Se o Instagram funcionar e o Elias confirmar que os Termos do ML permitem. Teste de 7 dias só com termos genéricos e as negativas "amazon", "kindle", "mercado livre" |
| Google PMax / TikTok | Sem tag ou pixel, a otimização fica cega. O pixel quebra a CSP | Fase 2, junto com a medição server-side da seção 5.3 |
| Telegram Ads | O mínimo de verba é alto e o pagamento é em TON | Não vale nessa escala |

**Custo zero, junto com o pago** (fora do escopo de agents): divulgar o canal no perfil do Instagram do site e em grupos e fóruns de leitores onde as regras permitem.

## 4. Escopo do MVP

Entra:
1. **Página `/vitrine/`**, gerada pelo `build.py`:
   - sai do mesmo `page()` da home: hero, destaques e seções, com o mesmo `card()` e o mesmo rodapé (aviso de associado, "preço final é o da loja", horário da verificação);
   - cada link de compra (card, hero, botões de loja) aponta para `/r/<id>/ads`, e a outra loja para `/r/<id>/<loja>/ads`. Se isso dobrar as regras, a outra loja usa a rota sem tag (decisão do `frontend-developer`, conferindo o `MAX_REDIRECTS`);
   - `<meta name="robots" content="noindex">`, canonical para a home, fora do menu e do sitemap, e `vitrine` no `RESERVED`;
   - o menu e os links internos continuam iguais. Quem navega para outra página sai da tag `ads` e conta como site. Essa perda é aceita;
   - **banner secundário do Telegram no topo:** "Receba as ofertas no Telegram", com o link de convite exclusivo do canal (constante `TG_ADS_INVITE` no `build.py`, que é público por natureza). É uma linha discreta, sem modal e sem empurrar a vitrine para baixo da dobra no celular.
2. **Rota `/r/<id>/ads`** com a tag `AMAZON_TAG_ADS` (`ofertaslivrads-20`), só para os livros que aparecem na vitrine. Com as cerca de 15 ofertas ativas de hoje, são cerca de 15 linhas a mais, longe do `MAX_REDIRECTS = 2000`. No ML, ela usa o mesmo `ml_url`, como `/tg`, `/wa` e `/bot` já fazem.
3. **`AMAZON_TAG_ADS` no `deploy.yml`**, como as outras tags de canal.
4. **Uma frase na `/privacidade/`:** "Se você chegou por um anúncio, a plataforma do anúncio (como a Meta) tem os dados dela. O site não envia nenhum dado seu para ela."
5. **Bloco "Anúncios" no `/painel`** (opcional no MVP, decisão 10):
   - views de `/vitrine/`, cliques em `/r/*/ads` e vendas da tag `ads`, por dia, a partir do `daily_rollup` e da `sales`, que já existem;
   - o gasto, que o Elias lê no Ads Manager.

Fica fora, e quando vale:
- **Conversions API da Meta e conversões offline do Google:** ver a seção 5.3. Vale se o "Maximizar cliques" trouxer clique ruim (views de `/vitrine/` ÷ cliques do Meta < 60%) ou na fase 2.
- **UTM:** o GraphQL da zona no Free **não guarda query string** (teste F0 em `docs/produto/analytics.md`). Por isso a atribuição é pelo caminho (`/vitrine/`, `/r/*/ads`) e pela tag. Pôr UTM no anúncio não atrapalha, mas não é usada.
- **Tag `ads` também nas páginas internas** (nichos, livro) para quem veio do anúncio: exigiria cookie ou Worker. Fica fora.
- **Contagem diária de membros do canal no painel** (`getChatMemberCount` no cron do Worker): vale se o teste for escalado. No teste, o número do link de convite no Telegram basta.

## 5. Medição

### 5.1 O que mede cada etapa

| Etapa | Métrica | Fonte |
|---|---|---|
| Impressão → clique | CPM, CTR do link, CPC | Ads Manager |
| Clique → página | views de `/vitrine/` (bot = 0) ÷ cliques do Meta | `daily_rollup` (D1) |
| Página → loja (**principal**) | cliques em `/r/*/ads`; **custo por clique de saída** = gasto ÷ cliques em `/r/*/ads` | `daily_rollup` |
| Venda (**principal**) | vendas e comissão da tag `ofertaslivrads-20`; **custo por venda** = gasto ÷ vendas `ads` | tabela `sales` (CSV "Produto relacionado" pelo `analytics/vendas.py`), D+1 |
| Página → canal (secundária) | entradas pelo link de convite "anuncios-meta" | Telegram: canal > Links de convite |
| Progresso da Creators API | query `vendas_30d` que já está no `analytics.md` | D1 |

A venda pela tag `ads` é limpa: só a `/vitrine/` usa essa tag. A venda de quem entra no canal pelo banner cai na `tg`, misturada com a orgânica, e por isso fica como secundária.

### 5.2 Por que isso não quebra a CSP nem a LGPD

- Nada muda no navegador: sem pixel, sem script novo, sem cookie. O `_headers` não muda.
- Nenhum dado pessoal sai do nosso lado para a Meta. O `fbclid` que a Meta põe na URL chega ao Cloudflare como em qualquer acesso e não é guardado: o rollup não tem query string.
- A frase nova na `/privacidade/` é só transparência. Ela não muda a base legal, porque não há tratamento novo.

### 5.3 Medição server-side (fase 2, fora do MVP, PR sensível)

Se for preciso otimizar por conversão:
- um Worker em `/r/*/ads` chama a **Conversions API** da Meta com um evento de clique de saída, antes do 302;
- isso tira o `/r/` do `_redirects` estático e põe a cota do Worker no caminho do clique de afiliado. Também mexe na rota `/r/`;
- a CAPI pede IP, user agent e `fbc` para casar o evento. Isso é **compartilhar dado pessoal com a Meta para publicidade**: pela LGPD, exige consentimento, ou uma avaliação de legítimo interesse com teste de balanceamento, além de aviso específico na `/privacidade/` e opt-out;
- consentimento sem JS de terceiro é possível (um formulário e um cookie primário), mas acrescenta um banner ao site, que hoje não tem cookie nenhum.

**Recomendação:** só fazer se a fase 1 der custo por venda aceitável, e com spec própria. O Google (enhanced e offline conversions) tem o mesmo peso de LGPD e fica fora.

## 6. Orçamento de teste

**Premissas para os limites:**
- CPC no Instagram de R$ 0,40;
- 25% dos visitantes da vitrine clicam numa oferta, o que dá **R$ 1,60 por clique de saída**;
- 5% dos cliques de saída viram venda, o que dá **cerca de R$ 32 por venda**.

Com R$ 350, isso daria cerca de 220 cliques de saída e cerca de 11 vendas `ads`, o suficiente para a Creators API. O equilíbrio só pela comissão seria R$ 0,20 por clique de saída (R$ 4 × 5%), inalcançável. Por isso os limites medem o custo da Creators API, não o lucro.

| Item | Valor |
|---|---|
| Verba diária | **R$ 25** em 1 campanha e 1 conjunto: Brasil, 18+, público Advantage+ com sugestão de interesse em livros e leitura, **sem** interesse "Kindle" ou "Amazon" |
| Posicionamentos | manuais: Instagram Feed, Stories e Reels. Facebook, Messenger e Audience Network desligados |
| Duração | **14 dias**, de 2026-11-10 a 2026-11-23. Fica antes da semana da Black Friday, quando o CPM sobe, e termina com dado para decidir a BF |
| Teto total | **R$ 350**. Configurar o limite de gasto da conta no Meta em R$ 400 |
| Aprendizado | não mexer nos primeiros 3 dias, salvo regra de corte por criativo |

**Corte:**
- **Criativo:** com R$ 40 gastos, CPC acima de R$ 1,00, ou CTR do link abaixo de 0,8% no Feed e 0,5% em Stories e Reels → pausar o criativo.
- **Campanha, no dia 7** (cerca de R$ 175):
  - custo por clique de saída acima de **R$ 3,00** → parar;
  - ou 0 vendas `ads` com 80 ou mais cliques em `/r/*/ads` (o esperado seriam cerca de 4) → parar;
  - views de `/vitrine/` ÷ cliques do Meta abaixo de 60% → parar e investigar (clique acidental ou bot).
- **Conta:** aviso de política da Meta ou qualquer e-mail da Amazon ou do ML sobre a conta de afiliado → parar tudo na hora.

**Escala:**
- custo por clique de saída ≤ **R$ 1,20** e custo por venda `ads` ≤ **R$ 35** (10 vendas por cerca de R$ 350 por mês, o preço de manter a Creators API) → subir 20% a cada 3 dias, até R$ 60 por dia. A Black Friday (27/11 a 30/11) é decisão do Elias no dia 23;
- custo por clique de saída entre R$ 1,20 e R$ 3,00 → manter até o fim e decidir pelo custo por venda.

**Secundária:** custo por membro do canal (gasto ÷ entradas pelo convite). Não decide corte nem escala; entra no relatório.

**Relatório do dia 7 e do dia 14:** gasto, CPC, CTR por posicionamento, views, cliques em `/r/*/ads`, custo por clique de saída, vendas e comissão `ads`, custo por venda, entradas no canal e `vendas_30d`.

## 7. Criativos

- **Quantidade:** 4 criativos no conjunto, 2 formatos × 2 mensagens:
  - formatos: **1080×1350** (4:5, Feed) e **1080×1920** (9:16, Stories e Reels). O vertical pode ser imagem estática ou um vídeo curto de 6 a 10 s com a tela da vitrine rolando, deixando livres as margens de cima e de baixo, onde o Instagram põe a interface;
  - mensagem A, **histórico**: "Desconto de verdade? A gente mostra o menor preço dos últimos 90 dias.";
  - mensagem B, **vitrine**: "Ofertas de livros conferidas a cada hora, com o horário da verificação.".
- **Marca:** tokens de `docs/marca/spec-visual.md`:
  - Fraunces 700–800 com SOFT/WONK no título e Outfit no texto;
  - paleta da marca, fundo com grão e capa como objeto (inclinada, com sombra);
  - a Mavi (`static/mavi.svg`) como assinatura;
  - logo `static/logo.svg`.
- **Proibido no criativo:**
  - nome ou logo da Amazon e do Mercado Livre (seção 2.1);
  - preço;
  - "Black Friday" antes da faixa do site estar ativa;
  - contagem regressiva, "últimas unidades", ranking ou "mais vendido" (regra de curadoria do CLAUDE.md).
- **Capas:**
  - nunca imagem vinda da Amazon (Licença 1(a));
  - capa de livro é obra protegida da editora. Na rodada 1, a mensagem A usa a **ilustração do gráfico de histórico** (`docs/marca/grafico-historico.md`) e capas genéricas desenhadas pela marca, sem capa real;
  - a mensagem B pode usar um print da vitrine, com as capas como aparecem no site e sem recorte de uma capa só em destaque;
  - se a Meta receber denúncia de PI, o criativo sai e não volta.
- **Texto do anúncio:** dizer que o site é de ofertas com link de afiliado ("ganhamos comissão, sem custo a mais para você"). Isso segue a Amazon 6(l), "não confundir o cliente sobre o relacionamento".
- **Quem faz:** o `brand-designer` entrega os 4 PNG ou MP4 fora do repo (ou em `docs/marca/anuncios/`, se o Elias preferir). O Elias sobe no Ads Manager.

## 8. Fluxo do usuário

1. A pessoa vê o anúncio no Feed, nos Stories ou nos Reels do Instagram.
2. Ela toca e abre `ofertaslivros.com.br/vitrine/?fbclid=...`, a mesma vitrine da home. A página é estática, abre rápido e funciona sem JS.
3. No topo, uma linha discreta: "Receba as ofertas no Telegram".
4. Ela rola, vê o preço, o selo de 90 dias e o horário da verificação, e toca numa oferta. O link `/r/<id>/ads` leva à Amazon com a `ofertaslivrads-20`, ou ao ML com o `ml_url`.
5. Se não comprar agora, pode tocar no banner e entrar no canal pelo link de convite "anuncios-meta". Depois compra por `/r/<id>/tg`.

## 9. Critérios de aceite

1. O build gera `dist/vitrine/index.html` com o mesmo conteúdo de `dist/index.html`, exceto: `noindex`, canonical para a home, os links de compra em `/r/<id>/ads` e o banner do Telegram. Teste no `selftest()`: tirando essas diferenças, o HTML das duas páginas fica igual.
2. `/vitrine/` não aparece no menu nem no sitemap, e `vitrine` está no `RESERVED`. A home e o `/ofertas/` continuam com `/r/<id>`, sem `ads`.
3. Nenhum link de compra da vitrine aponta para a loja direto nem para `/r/<id>` sem `ads`. O `_redirects` tem `/r/<id>/ads` **só** para os livros da vitrine:
   - na Amazon, com a tag de `AMAZON_TAG_ADS`, e com a tag do site se ela estiver vazia, como nas outras tags de canal;
   - no ML, com o mesmo `ml_url` validado pelo `ml_url()`.
   Teste no `selftest()`, inclusive com `AMAZON_TAG_ADS` inválida, que tem que falhar.
4. O total de regras do `_redirects` continua abaixo de `MAX_REDIRECTS`. O build falha, como já faz hoje, se passar.
5. O CSP, os outros headers e a allowlist ficam iguais. Nenhum script, nenhuma imagem ou fonte de terceiro, nenhum `<script>` inline.
6. Sem `TG_ADS_INVITE`, o banner não aparece e a página continua igual. Com ele, o banner tem um link `https://t.me/+...` com `rel="noopener noreferrer"`.
7. Sem JS, a página funciona por inteiro. Em 360 e 320 px:
   - sem rolagem horizontal;
   - o banner ocupa uma linha, com área de toque ≥ 44 px e contraste AA (conferido com `docs/marca/contraste.py`);
   - o hero continua na primeira dobra.
8. A `/privacidade/` tem a frase da seção 4, item 4, e nenhum outro texto muda.
9. `AMAZON_TAG_ADS` está no `deploy.yml`, igual às outras tags, e a action fica fixada por SHA, como já está.
10. Com o PR no ar, um teste manual: abrir `/vitrine/?fbclid=teste`, tocar numa oferta e ver o 302 para `amazon.com.br/dp/...?tag=ofertaslivrads-20`. No dia seguinte, `/vitrine/` e `/r/*/ads` aparecem no `daily_rollup`.
11. Bloco do painel (opcional): views de `/vitrine/`, cliques em `/r/*/ads`, custo por clique de saída (com o gasto digitado ou fixo, decisão do `alerts-engineer`) e vendas `ads` por dia, nos últimos 14 dias, sem JS e atrás do Access, como o resto do `/painel`.

## 10. Divisão por agent, em ordem

| # | Agent | Entrega | Sensível? |
|---|---|---|---|
| 0 | Elias | Seção 13: conta e perfil no Meta/Instagram, tag `ofertaslivrads-20` no Associates, var `AMAZON_TAG_ADS` no Environment `production`, link de convite "anuncios-meta" no canal, leitura dos Termos do ML | — |
| 1 | `brand-designer` | 4 criativos em 1080×1350 e 1080×1920 (seção 7). Não toca em código | Não |
| 2 | `infra-engineer` | `AMAZON_TAG_ADS` no `deploy.yml` | **Sim** (workflow e tag) |
| 3 | `frontend-developer` | `/vitrine/` (cópia da home pelo `page()` com o sufixo `ads` nos links), banner do Telegram, `/r/<id>/ads` só para os livros da vitrine, `RESERVED`, frase da `/privacidade/`, testes no `selftest()` | **Sim** (`_redirects`/`/r/`, tag, texto de privacidade) |
| 4 | `alerts-engineer` | (opcional) bloco "Anúncios" no `/painel` lendo o `daily_rollup` e a `sales` | **Sim** (Worker) |
| 5 | `security-auditor` | Revisa os PRs 2 e 3: allowlist intocada, tag validada, sem open redirect, CSP igual, link do Telegram só `https://t.me/` | — |
| 6 | `code-reviewer` + review do Codex | Fluxo normal de PR, com `web-design-guidelines` no PR 3. Merge dos PRs 2 a 4 só com "aprovado, pode seguir" do Elias na sessão | — |

O PR 3 depende do PR 2 só para a tag sair certa. Sem a var, o build cai na tag do site, então a ordem não quebra nada.

O `collector-engineer` não entra: não muda coleta.

## 11. Riscos

- **Banimento por violar o programa (crítico):**
  - anúncio apontando para `/r/` ou para a loja;
  - lance em "amazon" ou "kindle";
  - nome ou logo da loja no criativo;
  - imagem da Amazon no criativo.
  Tudo isso está proibido na seção 2.1. A configuração da campanha é do Elias, com o checklist da seção 12.
- **Exceção de navegador na regra 1:** mais tráfego não muda nada na leitura de preço, mas mais venda acelera a Creators API, que é a saída dessa exceção.
- **ML sem texto oficial lido:** a decisão 2 cobre esse caso.
- **Reprovação na Meta por página "ponte":** a vitrine tem conteúdo próprio (histórico, horário da verificação, curadoria). Se reprovar, a alternativa é apontar para `/black-friday/` ou para a home, com o clique medido pelo caminho, mas sem a tag `ads`.
- **Conteúdo duplicado:** a `/vitrine/` copia a home. O `noindex` e o canonical evitam que ela concorra com a home no Google.
- **Custo:** teto de R$ 400 no limite de gasto da conta e regras de corte. O agent nunca tem acesso ao Ads Manager nem ao cartão.
- **LGPD:** o MVP não cria tratamento novo de dado pessoal. A CAPI (seção 5.3) cria, e por isso fica para spec própria.
- **`MAX_REDIRECTS`:** a rota `ads` só existe para os livros da vitrine. Se o número de ofertas ativas crescer muito, o build falha antes do deploy, como já faz hoje.
- **Conta pessoal do Elias na Meta:** a conta de anúncio fica num portfólio empresarial, com 2FA. O perfil do Instagram não pode ter "Amazon" no nome (Requisitos 1(g)). "Só Mais um Livro - Ofertas Livros" serve.

## 12. Checklist da campanha (o Elias confere antes de publicar)

- [ ] URL de destino: `https://ofertaslivros.com.br/vitrine/`, nunca `/r/`, nunca a loja, nunca a home.
- [ ] Posicionamentos manuais: só Instagram Feed, Stories e Reels.
- [ ] Nenhum interesse com "Amazon", "Kindle" ou "Mercado Livre", e o criativo sem esses nomes, sem logos e sem preço.
- [ ] Limite de gasto da conta em R$ 400 e orçamento de R$ 25 por dia.
- [ ] Texto com a menção a link de afiliado.

## 13. Decisões em aberto para o Elias

Decididas em 2026-11-07: o destino é o site (vitrine com a tag `ads`, com o Telegram só como banner) e o canal é o Meta, só Instagram, com posicionamentos manuais.

1. **Fazer o teste ou não.** A conta (seção 3) diz que a comissão de livro não paga anúncio. O teste é uma aposta estratégica: Creators API e base para a Black Friday. Default: fazer, com teto de R$ 350.
2. **Termos do ML:** abrir os Termos de Afiliados e Criadores no portal, logado, e confirmar se tráfego pago para página própria é permitido. Se não for, a vitrine do anúncio mostra só ofertas da Amazon.
3. **Orçamento:** R$ 25 por dia × 14 dias (R$ 350), com teto de R$ 400 na conta.
4. **Criar as contas:** portfólio empresarial e conta de anúncio da Meta, com 2FA e forma de pagamento, e o perfil do Instagram ligado a ela. Só o Elias pode fazer.
5. **Tag `ofertaslivrads-20`:** criar no Associates Central e gravar `AMAZON_TAG_ADS` no Environment `production`. Criar também o link de convite "anuncios-meta" no canal.
6. **Sites cadastrados na Amazon:** conferir se o canal do Telegram e o do WhatsApp estão em "Seus sites e aplicativos".
7. **Capas no criativo:** rodada 1 sem capa real (recomendado), ou com o print da vitrine já na rodada 1.
8. **Limites de corte e escala** (seção 6): corte em R$ 3,00 por clique de saída no dia 7, ou 0 vendas com 80 ou mais cliques de saída; escala com até R$ 1,20 por clique de saída e até R$ 35 por venda.
9. **Caminho da página:** `/vitrine/` (recomendado) ou `/ofertas/`. O `/ofertas/` já existe: é indexado, está no menu e tem venda orgânica. Usar esse caminho tira o SEO dele e mistura as vendas.
10. **Bloco "Anúncios" no `/painel`:** agora, ou a conta manual por 14 dias (default: manual).
11. **Black Friday:** no dia 23/11, com o relatório do dia 14, decidir se a campanha segue de 27 a 30/11, quando o CPM sobe.
