# Pedido de livro (formulário "Pedir um livro")

Status: spec, 2026-10-20. **PR SENSÍVEL** (CSP em `_headers`, entrada de usuário, texto de privacidade).

## 1. Problema e usuário
O visitante que não achou um livro quer pedir que ele seja monitorado, sem ter Telegram. Hoje o FAB e o botão do capítulo do alerta (`build.py`, `fab()` e linha ~900) abrem o bot. O formulário tira o Telegram do caminho e dá ao Elias a lista do que o público quer. Isso alimenta a curadoria: livro pedido que entra em oferta vira clique de afiliado.

**Referência:** o ofertasdiscos.com tem a seção "Pedir um disco", mas o HTML servido não traz o form (conferido com WebFetch em 2026-10-20; nada foi enviado). Dela copiamos o FAB e a ideia do pedido. Não copiamos o form montado em JS, porque aqui o site precisa funcionar sem JS, nem campos de contato.

## 2. Caminho escolhido: Netlify Forms
| | (a) Netlify Forms | (b) Rota POST no Worker |
|---|---|---|
| Código novo | nenhum backend; só HTML no `build.py` | script no Worker `ofertaslivros` (`main` e `run_worker_first`), binding de e-mail, testes |
| Custo | submissões grátis e ilimitadas nos planos por crédito ("Forms submissions: Free", [Billing FAQ](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/billing-faq-for-credit-based-plans/)). O POST conta como web request (2 créditos por 10 mil). | Email Service: o envio para destino verificado é "free on all plans", mas a tabela do Free diz "Not available" para Email Sending ([pricing](https://developers.cloudflare.com/email-service/platform/pricing/)), uma contradição na própria doc. Destino arbitrário exige o Workers Paid. Resend: chave de API e DNS de envio a mais. |
| E-mail / DNS | o destino fica no painel do Netlify, sem DNS novo | exige Email Routing (MX do Cloudflare) numa zona. No `.com`, isso briga com o MX da Titan, que o `infra-engineer.md` manda não tocar. Só caberia no `.com.br`. |
| Anti-spam | Akismet automático + honeypot (`netlify-honeypot`) ([spam filters](https://docs.netlify.com/manage/forms/spam-filters/)). Só submissão verificada gera e-mail. | tudo por nossa conta (honeypot, tamanho, rate limit) |
| Limite | se os créditos do Netlify acabarem, o site **e** o form pausam até o mês seguinte ([Billing FAQ](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/billing-faq-for-credit-based-plans/)) | 100 mil req/dia no Workers Free |

**Recomendação: (a).** Zero código de servidor, custo zero e nenhuma mexida em MX. Os dois domínios postam para o `.com`.
- No `.com.br` (Cloudflare), o POST vai para outra origem. Um POST de form HTML é navegação e não precisa de CORS. O Netlify identifica o form pelo campo `form-name`, mas a doc não diz se ele confere a origem. **Isso precisa de teste antes do merge** (critério A7).
- O Netlify só injeta o `form-name` no HTML que ele mesmo serve ([setup](https://docs.netlify.com/manage/forms/setup/)). Por isso o `build.py` escreve o `<input type="hidden" name="form-name" value="pedido">` explicitamente, senão o form do `.com.br` não seria reconhecido.
- A detecção roda no pós-processamento do deploy. A doc não fala do deploy por zip na API, que é o que o `deploy.yml` usa, então isso também entra no critério A7.

O (b) só vale se o Netlify sair do projeto (rollback do `.com` para o Worker).

## 3. Escopo do MVP
- Página `/pedir/` com o form e página `/pedir/recebido/` de confirmação, ambas geradas pelo `build.py` e servidas nos dois domínios.
- O FAB e o "Pedir um livro" do capítulo do alerta passam a apontar para `/pedir/`. O bot continua no capítulo, como "Me avise se baixar".
- Campos: `titulo` (obrigatório) e `autor` (opcional). Nada de nome, e-mail ou telefone.
- Sem JS novo: `static/app.js` fica intocado e `connect-src` continua `'none'`.

**Fora do MVP:**
- O painel creme do FAB (`spec-visual.md` 9.5). Vale quando o form estiver validado. Dá para fazer com o atributo `popover`, sem JS, e o `/pedir/` continua como fallback.
- O envio por fetch sem recarregar. O Netlify não manda CORS, então a resposta não seria legível a partir do `.com.br`. O ganho é pequeno.
- Avisar o visitante, a lista pública de pedidos e o reCAPTCHA (script de terceiro, proibido pela CSP).

## 4. Fluxo
1. O visitante toca no FAB e abre `/pedir/` (link comum, funciona sem JS).
2. Preenche o título e, se quiser, o autor, e envia. É um `POST` para `https://ofertaslivros.com/pedir/recebido/` (URL absoluta, igual nos dois domínios).
3. O Netlify grava a submissão, roda o Akismet e o honeypot e devolve a página `/pedir/recebido/`: "Recebemos seu pedido. Não respondemos um a um: se o livro entrar em oferta, ele aparece no site e nos canais." A página traz um link de volta para a home.
4. Se a submissão for verificada, o Netlify manda o e-mail para o endereço configurado no painel.

HTML esperado (o `frontend-developer` ajusta classes e textos):
```html
<form name="pedido" method="POST" action="https://ofertaslivros.com/pedir/recebido/" netlify netlify-honeypot="site" accept-charset="utf-8">
  <input type="hidden" name="form-name" value="pedido">
  <p class="sr" aria-hidden="true"><label>Não preencha <input name="site" tabindex="-1" autocomplete="off"></label></p>
  <label>Título <input name="titulo" required maxlength="150" autocomplete="off"></label>
  <label>Autor (opcional) <input name="autor" maxlength="100" autocomplete="off"></label>
  <button type="submit">Enviar pedido</button>
</form>
```
O `SITE` do `build.py` já é `https://ofertaslivros.com`. A action deve sair dele, e não de uma string solta.

## 5. Anti-spam e limites
- **Honeypot** `site`, visualmente oculto e fora do tab. O Netlify descarta em silêncio.
- **Akismet** automático. Spam não gera e-mail.
- **Tamanho:** `maxlength` 150 (título) e 100 (autor), mais `required` no título.
  - **Limite conhecido:** o Netlify não valida tamanho no servidor (o teto é o de 8 MB por request), e o plano Free não tem rate limit configurável. Um bot que ignore o HTML passa.
  - Mitigação: só o verificado vira e-mail, e o Elias pode desligar a notificação no painel.
  - Se o spam aparecer, partir para o (b), que tem validação e rate limit próprios.
- **Relay de e-mail:** impossível. O destino é fixo no painel e não existe campo de e-mail, então também não há Reply-To.
- **Injeção de cabeçalho:** não montamos cabeçalho nenhum; quem monta é o Netlify.
- **XSS no e-mail:** o texto chega como texto no e-mail do Netlify. No site, nada do pedido é exibido.
- **CSRF:** irrelevante. Não há sessão nem ação autenticada, e qualquer um pode enviar.

## 6. CSP (`HEADERS` no `build.py`)
Valor mínimo, o mesmo nos dois domínios (o `_headers` é um só):
```
form-action https://ofertaslivros.com
```
Ele troca o `form-action 'none'`. No `.com` isso equivale a `'self'`, e no `.com.br` libera só o POST para o `.com`. Sem `www`, porque a action usa a raiz. O `connect-src 'none'` não muda.

## 7. Dados e LGPD
- **O que o visitante manda:** título e autor. Isso não é dado pessoal.
- **O que o provedor registra:** o Netlify guarda, junto com a submissão, o IP, o user agent e o referrer (campos que a API de submissions devolve; o infra-engineer confirma no primeiro teste). O IP **é** dado pessoal pela LGPD, porque permite identificar com dado adicional.
- **Onde fica:** na lista de submissões do form `pedido`, no projeto Netlify, e na caixa de e-mail do Elias.
- **Retenção:** 30 dias. Um step no `deploy.yml`, que já tem o `NETLIFY_AUTH_TOKEN` e roda várias vezes ao dia, lista `GET /api/v1/sites/$NETLIFY_SITE_ID/submissions` e apaga com `DELETE /api/v1/submissions/<id>` o que tiver mais de 30 dias. O e-mail na caixa do Elias é responsabilidade dele (decisão 3).
- **Como remover:** o pedido é anônimo e o visitante não tem como provar que é dele. A política diz que ele some em 30 dias, e o Elias decide se publica um contato para pedidos de remoção (decisão 4).
- **Texto novo em `privacy()`, seção "No pedido de livro":** "Guardamos só o título e o autor que você escrever. O formulário é processado pelo Netlify, que registra o endereço IP e o navegador junto com o pedido. Apagamos os pedidos em até 30 dias."
- **Correção no mesmo PR:** a seção "No site" diz que o site é hospedado na Cloudflare. O `.com` está no Netlify desde 2026-10-20, então o texto passa a ser "na Cloudflare e no Netlify".

## 8. Critérios de aceite
`python3 build.py --selftest`, sem rede:
- **A1.** `/pedir/index.html` tem exatamente um `<form`, com:
  - `method="POST"`;
  - `action` igual a `SITE + "/pedir/recebido/"`;
  - `name="pedido"`;
  - o hidden `form-name=pedido`;
  - o atributo `netlify-honeypot="site"` e o input `site`;
  - `titulo` com `required maxlength="150"` e `autor` com `maxlength="100"`;
  - nenhum input `email`, `tel` ou `nome`.
- **A2.** `/pedir/recebido/index.html` existe, tem `noindex` e não tem `<form`.
- **A3.** O FAB e o CTA "Pedir um livro" da home apontam para `/pedir/`, não para `t.me`. A asserção de hoje (`"<form" not in h`, linha ~1836) vira "a home não tem `<form`" (o form fica só em `/pedir/`).
- **A4.** A CSP do `HEADERS` é igual à de hoje, trocando só `form-action 'none'` por `form-action https://ofertaslivros.com` (atualizar a asserção da linha ~2157).
- **A5.** `privacy()` contém "pedido de livro", "Netlify", "IP" e "30 dias".
- **A6.** Nenhum `<script` inline novo e `app.js` sem mudança.

Depois do deploy, pelo `infra-engineer`, antes de dar como pronto:
- **A7.** O form `pedido` aparece em Netlify → Forms após o deploy por zip.
  - Um envio real a partir de `https://ofertaslivros.com.br/pedir/` cai em Verified e chega por e-mail, sem erro de CSP no console.
  - Um envio com `site` preenchido não aparece.
  - Se o envio pelo `.com.br` falhar, o PR para e voltamos à comparação da seção 2.
- **A8.** O step de limpeza apaga uma submissão com mais de 30 dias (testar com limite de 0 dias, uma vez).

## 9. Divisão por agent (ordem)
1. **Elias (painel do Netlify, projeto `aquamarine-sfogliatella-36f7b7`):**
   - Forms → **Enable form detection**;
   - depois do primeiro deploy, Project configuration → Notifications → Emails and webhooks → Form submission notifications → **Add notification → Email notification**, form `pedido`, com o endereço de destino.
   O endereço fica só no Netlify: fora do repo, do HTML e dos secrets.
2. **frontend-developer:** cuida do `build.py` (páginas `/pedir/` e `/pedir/recebido/`, `fab()`, CTA do capítulo do alerta, `HEADERS`, `privacy()`, selftest A1 a A6) e do CSS do form em `static/style.css`, com inputs de 46px conforme a spec 9.5.
3. **infra-engineer:** step de limpeza de 30 dias no `deploy.yml` (sensível), testes A7 e A8 e a conferência de headers nos dois domínios.
4. **security-auditor:** revisão da CSP, do honeypot, do step novo (o token só no step) e do texto de privacidade.
5. **code-reviewer** e depois o review do Codex. O PR é **sensível**: o merge só acontece depois do "aprovado, pode seguir" do Elias na sessão.

`collector-engineer` e `alerts-engineer` não participam.

## 10. Riscos
- **Credenciais:** nenhuma nova. O token do Netlify só aparece no step novo.
- **Dependência do Netlify:** se os créditos acabarem, o form para junto com o `.com`, e o `.com.br` fica com um form que posta para um site pausado. É aceitável, porque é raro e visível em Usage.
- **Rollback do `.com` para o Worker:** o form quebra. É preciso trocar para o (b) ou esconder o FAB. Isso deve ficar registrado no `infra-engineer.md`.
- **Spam sem validação no servidor:** ver a seção 5.

## 11. Decisões em aberto para o Elias
1. O e-mail de destino é o da Titan no `.com` ou outro? Fica só no painel do Netlify.
2. O autor é opcional (recomendado) ou obrigatório?
3. Retenção: 30 dias no Netlify está bom? E na caixa de e-mail, você apaga ou mantém?
4. Publicar um contato na página de privacidade para pedidos de remoção ou dúvidas da LGPD? Recomendo, mas isso expõe um endereço no HTML.
5. Começar com o MVP numa página `/pedir/` e deixar o painel do FAB (spec 9.5) para depois?

## 12. Decisões do Elias (2026-10-20), que prevalecem sobre o texto acima
1. **Caminho:** Netlify Forms.
2. **Destino:** o e-mail de pedidos da Titan no domínio, configurado só no painel do Netlify (Forms → Notifications). Nunca no repo nem no HTML.
3. **Campos:** "Nome do livro" (obrigatório) e "Autor do livro" (opcional). O autor é o do livro, não quem pede.
4. **Retenção:** 30 dias, com o step do infra-engineer.
5. **Remoção:** sem contato de remoção, porque não pedimos dado de ninguém. A privacidade só diz que o Netlify registra IP e navegador e que os pedidos somem em 30 dias.
6. **Sem página nova:** o form fica no próprio botão flutuante, um `<details>` que abre sem JS. Isso substitui `/pedir/` e `/pedir/recebido/` dos §3 e §4.
   - **Sem JS:** o POST vai para `SITE/#pedido-recebido`. O Netlify devolve a home e o `:target` mostra "Recebemos seu pedido".
   - **Com JS** (`app.js`), só no `.com`: `fetch` para o `SITE`, e o aviso aparece no painel, sem sair da página. Com erro ou falha de rede, cai no envio normal (item 7).
   - **CSP:** `form-action` e `connect-src` passam a `https://ofertaslivros.com`. É a única mudança.
   - O "Pedir um livro" do capítulo do alerta (que abria o bot) sai. O botão flutuante é a única entrada.
   - O critério A7 continua valendo: o infra-engineer testa a detecção no deploy por zip e o envio a partir do `.com.br`.
7. **JS só no `.com`:** de outra origem (o `.com.br`), a resposta do fetch seria opaca, e o "Recebemos" apareceria mesmo com falha. Por isso, no `.com.br` vale o envio normal do form: o visitante volta em `ofertaslivros.com/#pedido-recebido`, e quem confirma é a resposta do Netlify. O `connect-src` continua sendo o `SITE`, porque o fetch roda só no próprio `.com`.
8. **Dependência:** a privacidade promete apagar em 30 dias. O PR do form só entra depois do PR do infra-engineer com o step de limpeza no `deploy.yml`.
