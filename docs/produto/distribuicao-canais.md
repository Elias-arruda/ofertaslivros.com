# Spec: distribuição das ofertas nos canais (Telegram e WhatsApp)

Status: proposta, 2026-10-18. Autor: product-manager. Base: `docs/produto/alerta-de-preco.md`, de onde vêm o pipeline, o bot e o storage. Nada aqui cria um segundo bot nem um segundo coletor.

## 1. Problema e usuário

**Em uma frase:** o leitor que não vai abrir o site todo dia segue um canal (Telegram ou WhatsApp) e recebe só as melhores ofertas curadas, com preço verificado e link de afiliado. É a principal alavanca para chegar às cerca de 10 vendas qualificadas na Amazon que liberam a Creators API.

- **Usuário:** quem já usa Telegram ou WhatsApp para receber promoções e quer poucas mensagens, todas boas. Não há cadastro: ele só segue o canal.
- **Por que dá dinheiro:** o canal leva a oferta até a pessoa sem anúncio pago, e cada post tem link de afiliado. A curadoria (poucas mensagens, todas com preço verificado) é o que segura o seguidor. Canal que manda muita mensagem perde seguidor.
- **Dado de usuário:** **nenhum.** Os dois canais são um para muitos e só de leitura, e não guardamos quem segue. O único identificador guardado é o `chat_id` do próprio Elias, que fica em Secret (seção 7).

## 2. Decisões já tomadas com o Elias (registradas, não reabrir)

1. **Telegram por conta própria, pela Bot API oficial,** no mesmo cron do GitHub Actions do pipeline. Um canal público de ofertas curadas. O bot que posta no canal é o mesmo bot dos alertas. Quem implementa é o alerts-engineer.
2. **WhatsApp manual no início.** O pipeline gera o texto pronto das ofertas do dia (foto, título, preço, preço anterior, selo de menor preço em 90 dias e link de afiliado validado pela allowlist). O Elias posta num **Canal do WhatsApp**, que é um para muitos (não um grupo).
3. **Nada de automação não oficial do WhatsApp** (whatsapp-web.js, Baileys e similares). Ela viola os termos do WhatsApp e traz risco de ban.
4. **Manda Boa (https://mandaboa.com): reavaliar depois.** Pelo que o próprio site diz, ele conecta o WhatsApp de forma não oficial (funciona como o WhatsApp Web, e o número pode ser banido). Também aposta em volume e no espelhamento de grupos de terceiros, o que vai contra a curadoria. Não mostra API para receber as nossas ofertas. E exige guardar as chaves e tags de afiliado lá. O plano Turma custa R$ 69,90/mês (5 grupos, 90 mensagens por dia). O gatilho e as condições estão na seção 9.

## 3. O que existe hoje (conferido no repo em 2026-10-18)

| Item | Existe? | Onde |
|---|---|---|
| Workflow com cron `*/30` e `concurrency` | Sim | `.github/workflows/pipeline.yml`, job `collect` |
| Coletor do ML e entrada manual da Amazon | Sim | `collector/collect.py`, `collector/amazon_prices.csv` |
| `price_history` append-only | Sim | CSV mensal no branch `price-history` (`price_history/AAAA-MM.csv`) |
| Catálogo com id estável | Sim | `collector/catalog.json` |
| Geração do `data/offers.json` a partir do histórico | **Não** | `offers.json` ainda é o exemplo à mão (`"_exemplo": true`). O workflow só coleta e grava o histórico |
| Build e deploy no workflow | **Não** | `build.py` roda local; não há passo de deploy |
| Link de afiliado validado | Sim | `build.py`: `affiliate_url(o, tag, aff)`, `check_url`, `ml_url`, `partner_tag`, `_env_id` |
| `/r/<id>` | Sim | `build.py:build` gera `dist/_redirects`, uma linha por oferta ativa |
| Formatação de preço e data | Sim | `build.py`: `brl`, `when` |
| Foto da capa | **Não** | O card usa `/capa.svg` genérico. Nem `offers.json` nem o catálogo têm um campo de imagem |
| Bot do Telegram | **Não** | Especificado em `alerta-de-preco.md`, ainda não implementado |

**Referência (ofertasdiscos.com, conferido em 2026-10-18):**
- Canais de WhatsApp e Telegram gratuitos e só de leitura, em `/whatsapp`, `/telegram` e `/canais`.
- O site diz "cada oferta chega no canal assim que é publicada", sem horário fixo.
- Os links `/r/...` levam o parâmetro `placement=` (`hero`, `featured`, `grid`, `trending`) para medir de onde veio o clique. Isso confirma a ideia de medir por origem. A nossa versão usa caminho, e não query string (seção 6).

**Dependências deste spec** (vêm da etapa 1 de `alerta-de-preco.md`, que não é escopo aqui):
- (a) o pipeline gerar `data/offers.json` real a partir de `price_history` + catálogo;
- (b) build e deploy no mesmo workflow. Sem deploy, o link `/r/...` do post daria 404.

## 4. WhatsApp: o que a API oficial permite (verificado em 2026-10-18)

- **Canal (Channels/newsletter):** a documentação oficial da Meta para a Cloud API **não menciona** Canais. Não encontrei nenhuma página da Meta que documente postar em Canal pela API. Em sentido contrário há só fontes não oficiais:
  - um tópico no fórum de desenvolvedores da Meta, cuja resposta é "No" ([thread](https://developers.secure.facebook.com/community/threads/839137344932813));
  - a documentação de um BSP, que lista Channels como "Not supported" ([360dialog](https://docs.360dialog.com/partner/waba-management/phone-number-and-hosting/using-whatsapp-app-and-cloud-api-simultaneously)).

  **Conclusão: não consegui confirmar pela Meta que dá; tudo indica que não dá.** Os serviços que dizem postar em Canal (Whapi e similares) usam conexão não oficial e caem na decisão 3.
- **Grupo:** existe a [Groups API oficial](https://developers.facebook.com/docs/whatsapp/cloud-api/groups), mas ela não serve para o nosso caso:
  - exige Official Business Account (OBA, o selo verificado);
  - os grupos são só por convite;
  - o limite é de **8 participantes por grupo**.

  Ela foi feita para atendimento e colaboração, não para transmissão. Além disso, a Cloud API cobra por mensagem de template.
- **Consequência:** o WhatsApp fica manual (decisão 2). Reabrir só se a Meta documentar Canais na Cloud API. Isso faz parte do gatilho da seção 9.

## 5. Escopo do MVP

**Dentro:**
- **Seleção das ofertas para os canais** (uma função só, usada pelos dois canais). Uma oferta é elegível se estiver ativa em `offers.json`, passar por `validate_offer` e tiver preço fresco:
  - ML: `checked_at` de até 2 h;
  - Amazon: `checked_at` de até 12 h. É mais estrito que as 24 h do alerta, porque o post é público e fica no histórico do canal.

  E precisa ter pelo menos um destes motivos:
  - o selo "menor preço em 90 dias" é válido (ver o risco 12.3);
  - ou o desconto sobre `list_price_cents` é de pelo menos 30% (valor inicial, ver decisão 3).

  Ordenação: primeiro as que têm selo, depois o maior desconto, e no desempate o `checked_at` mais recente.
- **Canal do Telegram, automático:**
  - Um passo no workflow, depois do deploy, posta no canal pelo bot.
  - Janela das 08h às 22h BRT. No máximo 2 posts por execução e 8 por dia.
  - Uma oferta elegível fora da janela espera a manhã seguinte, desde que continue elegível (fresca e ativa) na hora de postar.
- **Resumo do WhatsApp, manual:**
  - Uma vez por dia, na primeira execução depois das 11h BRT, o bot manda **para o chat privado do Elias** as até 5 melhores ofertas elegíveis, já no formato do WhatsApp (seções 6 e 8). O Elias copia e cola no Canal do WhatsApp.
  - O horário fica depois da conferência manual da Amazon, que é de manhã, para que a Amazon entre fresca.
- **Deduplicação por canal** (seção 6).
- **Link por canal** em `/r/<id>/tg` e `/r/<id>/wa`, com tracking ID da Amazon por canal (seção 6).
- **Foto:** a do ML vem da API de itens (`thumbnail`/`pictures`). A Amazon fica sem foto até a Creators API (ver "Fora").
- **Mensagem fixada e descrição do canal** nos dois canais. Elas trazem o aviso de associado, a frase "o preço final é o da loja", o link do site e o link do bot de alertas.
- **Links para os canais no site:** no rodapé e numa página `/canais/`, só HTML.

**Fora (e quando vale fazer):**
- **Foto da Amazon.** Sem a Creators API não há fonte permitida: tirar da página da Amazon é scraping (regra 1). **Quando:** a Creators API for liberada, porque ela devolve as imagens. Alternativa antes disso: a capa do Open Library por ISBN (decisão 4). Até lá o post da Amazon sai só com texto, e Telegram e WhatsApp montam a prévia do link do lado deles.
- **WhatsApp automático.** **Quando:** o gatilho da seção 9 disparar.
- **Editar ou apagar no canal o post de uma oferta que venceu.** O link `/r/` de oferta vencida cai na home (critério 12), e isso basta. **Quando:** houver reclamação de "oferta não existe mais".
- **Post na hora para "oferta relâmpago"**, furando o limite diário. **Quando:** o canal tiver volume que justifique.
- **Contador próprio de cliques** (Worker no `/r/`, log). O `_redirects` estático não gera log que possamos ler, e um Worker é backend. **Quando:** os relatórios das lojas (seção 6) não bastarem.
- **Grupo do Telegram ou do WhatsApp com conversa.** Exige moderação e vai contra a curadoria.
- **Lista de desejos do bot ligada ao canal** (ex.: "segue o canal, quer alerta deste livro?"). **Quando:** o alerta de preço estiver no ar.

## 6. Regras de operação

### Frequência e horário

| Canal | Quando sai | Limite |
|---|---|---|
| Telegram | A cada execução do cron (30 min), das 08h às 22h BRT | 2 por execução, 8 por dia |
| WhatsApp (resumo para o Elias) | 1 vez por dia, na primeira execução depois das 11h BRT | até 5 ofertas |

Os horários e limites são constantes no código, não config. Quem quiser mudar, muda o número e abre PR.

### Deduplicação

- Log `channel_posts.csv` no branch `price-history`, append-only e gravado no mesmo passo "Gravar histórico" que já existe. Colunas: `posted_at` (UTC ISO), `channel` (`tg` | `wa`), `offer_id`, `store`, `price_cents`.
  - Não tem dado de usuário, então pode ser público.
  - O `message_id` do Telegram fica fora: ninguém o usa no MVP.
- Regra, por par `(offer_id, channel)`:
  - não repostar a mesma oferta por **7 dias**;
  - exceção: se o preço novo for **menor** que o último postado naquele canal, pode repostar depois de 24 h.
- O resumo do WhatsApp conta como postado no momento em que é enviado ao Elias. Não temos como saber se ele colou.
- "Já enviei o resumo hoje?" sai do mesmo log (há linha `wa` com `posted_at` na data BRT de hoje). Não precisa de estado extra.
- Idempotência: a linha do log só é escrita depois do `ok: true` do Telegram, e o `concurrency` do workflow impede duas execuções juntas.
  - Limite conhecido: se o job morrer entre o envio e o push do log, o post se repete uma vez na execução seguinte.
  - `ponytail`: aceito no MVP. A correção é gravar e dar push do log antes de enviar, se isso acontecer na prática.

### Link e medição de cliques por canal

- O `build.py` passa a gerar, para cada oferta ativa, três linhas estáticas no `_redirects`. As três apontam para um destino montado por `affiliate_url` e validado por `check_url`:
  ```
  /r/<id>     <url com tag do site>   302
  /r/<id>/tg  <url com tag do Telegram> 302
  /r/<id>/wa  <url com tag do WhatsApp> 302
  ```
- **Por que caminho e não `?c=tg`:**
  - a documentação do `_redirects` da Cloudflare marca o match por query parameter como não suportado;
  - não documenta se a query de entrada é repassada ao destino ([fonte](https://developers.cloudflare.com/workers/static-assets/redirects/));
  - e o destino da Amazon já tem `?tag=`.

  Com caminho fixo, nenhum valor que vem da requisição chega ao destino. A allowlist fica igual: continuam só IDs de `offers.json` e hosts de `ALLOWED_HOSTS`.
- **Amazon:** um tracking ID por canal, criado pelo Elias no painel dos Associados (ex.: `<base>-20` para o site, `<base>tg-20` e `<base>wa-20`). O relatório da Amazon por tracking ID mostra cliques, pedidos e comissão por canal. **É a medição do MVP, sem código de contagem.**
  - As tags entram em `vars` do repo, `AMAZON_TAG_TG` e `AMAZON_TAG_WA`. Não são segredo, porque aparecem na URL.
  - São lidas por `_env_id` (validação `TAG_RE`) e passadas no argumento `tag` que `affiliate_url` já recebe.
- **ML:** o build exige `matt_word == ML_AFFILIATE_ID`, e o link vem do painel com um `matt_tool` por link. Medir por canal exigiria três links do painel por item, gerados à mão.
  - No MVP, `/tg` e `/wa` do ML apontam para o mesmo `ml_url`. Os cliques do ML ficam agregados no painel do ML.
  - Ver decisão 2.
- Limite do `_redirects`: 2.000 regras estáticas. Com 3 linhas por oferta, cabem cerca de 660 ofertas ativas. Hoje são dezenas.

### Formato da mensagem

O mesmo texto base nos dois canais, montado por uma função com `brl` e `when` do `build.py`. É sempre **texto puro**: no Telegram, sem `parse_mode`, como no critério 11 da spec de alerta. O título e o autor vêm de dado coletado e não podem virar formatação.

```
Menor preço em 90 dias
Torto Arado, de Itamar Vieira Junior
R$ 42,90 (de R$ 74,90, -42%)
Amazon · preço verificado em 18/10 às 08h47. O preço final é o da loja.
Link de afiliado: https://<dominio>/r/torto-arado/tg
```

- A linha 1 só aparece se o selo for válido. Se não houver desconto (`list_price_cents == price_cents`), a parte "(de ...)" some, igual ao card do site.
- O desconto usa o mesmo cálculo do card (piso, para não exagerar).
- **Telegram:**
  - Com foto (ML): `sendPhoto` com o texto na `caption` (limite de 1.024 caracteres, folgado).
  - Sem foto (Amazon): `sendMessage` com prévia de link.
  - O destino é `TELEGRAM_CHANNEL_ID` (`@username` do canal, em `vars`).
- **WhatsApp (DM ao Elias):** para cada oferta, o bot manda duas mensagens no chat privado do Elias:
  1. a foto, sem legenda, para ele salvar ou compartilhar (só no ML);
  2. o texto exato a colar, com `/wa` no link.

  Antes delas vai um cabeçalho, "Resumo WhatsApp de 18/10: 4 ofertas", e no fim vai "fim do resumo". Uma mensagem por bloco deixa a cópia em um toque no celular.

## 7. Onde sai o texto do WhatsApp: opções e recomendação

| Opção | Como o Elias usa | Prós | Contras |
|---|---|---|---|
| Artefato do Actions | Entra no GitHub, abre o run e baixa o zip | Zero dependência nova | Ruim no celular, onde ele posta no Canal. Não leva a foto de forma útil. Precisa de login |
| Arquivo no repo (ex.: `whatsapp/AAAA-MM-DD.txt` no branch `price-history`) | Abre o arquivo no GitHub | Fica histórico | O mesmo atrito no celular. Commit diário de texto que ninguém relê |
| **DM do bot ao Elias** | Recebe no Telegram do celular, copia e cola | Chega sozinho no aparelho em que ele posta. Reusa o bot e o envio que já existem. A foto vem junto | Depende do Telegram estar no ar. Um `chat_id` a mais para guardar |

**Recomendação: DM do bot ao Elias.**
- O `chat_id` dele fica no GitHub Secret `TELEGRAM_ADMIN_CHAT_ID`. É dado pessoal do próprio operador, com o consentimento dele, e não vai para o banco de alertas nem para log.
- O bot só manda o resumo para esse chat. Ele nunca responde "resumo" a outro chat (critério 9).
- Para remover, basta apagar o Secret.
- Não vale fazer um fallback por artefato: se o Telegram cair, o canal do Telegram também cai, e o resumo sai no dia seguinte.

## 8. Fluxo

**Pipeline (um job, nesta ordem):**
1. coletar;
2. gerar `offers.json` (dependência a);
3. build;
4. deploy (dependência b);
5. comandos e disparos do bot de alertas (outra spec);
6. **postar no canal do Telegram;**
7. **resumo do WhatsApp para o Elias,** se for a primeira execução depois das 11h BRT;
8. gravar histórico e `channel_posts.csv`.

Se o passo 3 ou 4 falhar, os passos 6 e 7 não rodam, para não publicar link que dá 404.

**Seguidor do Telegram:**
1. Acha o canal pelo site (rodapé ou `/canais/`) e segue.
2. Recebe de 0 a 8 posts por dia, das 08h às 22h.
3. Toca no link `/r/<id>/tg`, que redireciona com a tag do Telegram para a loja.

**Elias, uma vez por dia (meta: menos de 10 min):**
1. Lança os preços da Amazon de manhã (fluxo que já existe).
2. Por volta das 11h30, recebe no Telegram o "Resumo WhatsApp de DD/MM".
3. Para cada oferta: abre o Canal do WhatsApp, anexa a foto quando houver, cola o texto e envia.
4. Se uma oferta do resumo não estiver mais boa (ele conferiu e o preço subiu), simplesmente não posta. Não há nada a desfazer.

**Seguidor do WhatsApp:** igual ao do Telegram, com o link `/r/<id>/wa`.

## 9. Manda Boa: gatilho para reavaliar e condições

**Gatilho objetivo para reavaliar** (qualquer um dispara a reavaliação, não a contratação):
- o Canal do WhatsApp passar de **1.000 seguidores**; ou
- o Elias gastar mais de **15 min/dia** postando no WhatsApp por 2 semanas seguidas. A medida é o tempo anotado por ele, e uma proxy é a média de mais de 8 ofertas por dia no resumo; ou
- o tracking ID `wa` ter **mais cliques que o `tg`** por 4 semanas seguidas, o que mostra que o WhatsApp é o canal que vale automatizar; ou
- a Meta documentar o envio para Canal pela Cloud API. Nesse caso, **avaliar a API oficial primeiro**, antes de qualquer ferramenta.

**Condições, se for contratado:**
1. **Número separado,** um chip só para isso. Nunca o número pessoal do Elias nem o do administrador do Canal oficial. Um ban não pode levar junto o canal principal.
2. **Só ofertas próprias,** vindas do nosso pipeline (o mesmo texto e o mesmo link `/r/<id>/...`). **Nunca espelhar grupos de terceiros.**
3. **Só faz sentido se ele receber as nossas ofertas sem cópia manual,** por exemplo lendo um feed nosso (`offers.json` ou um RSS gerado pelo build). Se continuar exigindo colar oferta por oferta, não economiza o tempo que dispara o gatilho, e não vale contratar.
4. **Tags de afiliado:** passar só um tracking ID da Amazon próprio para ele (ex.: `<base>mb-20`), que pode ser desativado a qualquer momento. Nunca passar senha nem token de painel, e nunca as credenciais do ML ou da Creators API. Se ele exigir chaves de API, não contratar.
5. **LGPD:** num grupo, os membros veem o telefone uns dos outros e a ferramenta guarda esses números. Ela vira operadora de dado pessoal, e isso precisa entrar em `/privacidade/`. Se der, preferir o Canal ao grupo também lá.
6. Antes de contratar, conferir de novo se a conexão continua não oficial. Se tiver passado a usar a API oficial, o risco de ban cai e a condição 1 pode ser revista.

## 10. Critérios de aceite

Seleção e deduplicação (pytest, com relógio injetado):
1. Uma oferta do ML com `checked_at` de mais de 2 h, ou da Amazon de mais de 12 h, não é elegível.
2. Uma oferta sem selo válido e com desconto abaixo de 30% não é elegível.
3. A ordenação é: selo primeiro, depois desconto decrescente, depois `checked_at` mais recente.
4. A mesma oferta não sai de novo no mesmo canal em 7 dias. Com preço menor que o último postado, sai de novo depois de 24 h, e não antes.
5. A deduplicação é por canal: postar no `tg` não bloqueia o `wa`.
6. Rodar o passo duas vezes sobre o mesmo estado (log já com as linhas da 1ª vez) gera 0 envios na 2ª.

Telegram:
7. Fora das 08h–22h BRT, nenhum envio. Na janela, no máximo 2 por execução e 8 por dia, contados pelo `channel_posts.csv`.
8. O envio não usa `parse_mode`. Um título com `<b>`, `*x*` ou `[a](b)` chega literal.

WhatsApp:
9. O resumo só vai para `TELEGRAM_ADMIN_CHAT_ID`. Com o Secret ausente, o passo é pulado com aviso e sem erro, e nenhum outro chat recebe nada.
10. No máximo 1 resumo por dia BRT, mesmo que o workflow rode de novo depois das 11h.

Links e allowlist:
11. Para cada oferta ativa, o `_redirects` tem `/r/<id>`, `/r/<id>/tg` e `/r/<id>/wa`, todos com destino que passa por `check_url`. No destino Amazon do `/tg`, `tag=` é igual a `AMAZON_TAG_TG`. Uma tag fora de `TAG_RE` faz o build falhar.
12. A última linha do `_redirects` é `/r/* / 302`. Assim, um link de oferta vencida, já postado no canal, cai na home e não num 404. É o único curinga, e o destino é interno.
13. O texto do post contém só URLs do nosso domínio. Nenhuma URL de loja aparece no texto, nem crua nem sem passar pelo `/r/`.
14. A URL da foto só é aceita com `https` e host terminado em `.mlstatic.com`. Qualquer outra é descartada, e o post sai sem foto.

Regras do projeto:
15. Nenhum passo deste spec faz request HTTP a domínio da Amazon. Usar o mesmo teste de rede mockada do critério 2 da spec de alerta.
16. Os logs do workflow mostram só contagens ("tg: 2 postadas, wa: resumo com 4"). Não mostram token, `chat_id` nem texto de post.
17. Todo post tem "o preço final é o da loja", o horário da verificação e "Link de afiliado". A mensagem fixada dos dois canais tem o aviso de associado.

Site:
18. O rodapé e `/canais/` linkam o canal do Telegram (`https://t.me/<canal>`) e o do WhatsApp (`https://whatsapp.com/channel/<id>`), com `rel="noopener noreferrer"`, sem JS e com a CSP igual.

## 11. Divisão por agent (ordem de execução)

0. **Elias (pré-requisito):**
   - criar o canal público no Telegram e pôr o bot como administrador só com "Publicar mensagens";
   - criar o Canal do WhatsApp;
   - criar os tracking IDs `tg` e `wa` na Amazon;
   - cadastrar `vars` (`TELEGRAM_CHANNEL_ID`, `AMAZON_TAG_TG`, `AMAZON_TAG_WA`) e o Secret `TELEGRAM_ADMIN_CHAT_ID`;
   - escrever a mensagem fixada.

   Esperar a sessão que mexe em `build.py`, `data/`, `static/` e no coletor terminar.
1. **collector-engineer:**
   - dependências (a) e (b): gerar `offers.json` real no workflow, depois o build e o deploy;
   - incluir a URL da foto do ML no `offers.json` (já vem da API de itens, sem request extra se o `/items/bulk` trouxer `thumbnail`);
   - validar o host da foto (critério 14);
   - garantir a regra do selo de 90 dias (risco 12.3).
2. **frontend-developer:** no `build.py`:
   - as três linhas por oferta e o curinga no `_redirects` (critérios 11 e 12), reaproveitando `affiliate_url` e `_env_id`;
   - os links dos canais no rodapé e em `/canais/` (critério 18);
   - a função de texto do post (`brl`, `when`, desconto), que deve ficar no `build.py` ou num módulo importado por ele, para o site e os canais não divergirem.
3. **alerts-engineer:**
   - seleção, deduplicação e `channel_posts.csv`;
   - post no canal do Telegram e resumo para o Elias, como passos do `pipeline.yml` depois do deploy, usando o cliente do bot da spec de alerta;
   - critérios 1 a 10, 13, 15, 16 e 17;
   - conferir se `/setjoingroups` desligado atrapalha o bot como administrador de canal.
4. **security-auditor:**
   - o `_redirects` com curinga e as linhas por canal (open redirect);
   - o escopo dos secrets por passo: o token do bot só no `env` dos passos do bot, nunca no job inteiro;
   - os logs públicos (repo público);
   - a allowlist da foto.

   Rodar `/threat-model` incluindo o canal.
5. **code-reviewer:** um PR por etapa. Na etapa 2, com `web-design-guidelines`.

## 12. Riscos

**12.1 Regras inegociáveis**
- *Scraping da Amazon:* a foto da Amazon é a tentação aqui ("só pegar a imagem da página"). Isso é proibido: o post da Amazon sai sem foto até a Creators API, e o critério 15 trava no CI.
- *Credenciais:* o token do bot já é um Secret da spec de alerta. As tags e o `@` do canal vão em `vars`, porque não são segredo.
- *Open redirect:* as linhas novas são estáticas, geradas pelo build com destino validado. O curinga aponta para `/`. Nenhum dado da requisição vira destino.
- *Transparência:* o aviso de associado vai na mensagem fixada e "Link de afiliado" vai em todo post (critério 17).

**12.2 Política dos programas** (confirmar antes de lançar, ver decisão 1)
- **Amazon:** confirmar no Operating Agreement da Amazon.com.br que postar link de afiliado em canal público de Telegram e de WhatsApp é permitido. É mídia social pública, não e-mail nem mensagem privada, mas vale confirmar o texto.
- **Amazon:** confirmar também a exigência de aviso por post. E o que se pode dizer sobre um preço que não veio da API: o post mostra o horário da conferência manual.
- **DM ao Elias com link de afiliado:** é uso interno. Ele não deve clicar para comprar (compra própria não conta e pode violar o contrato). Isso vale como orientação para ele, não como código.

**12.3 Selo "menor preço em 90 dias" e o CDC**
- Hoje o `lowest_90d_cents` do exemplo é digitado à mão, e o `price_history` real começou agora.
- Um selo de "menor preço em 90 dias" sem 90 dias de histórico é afirmação falsa ao consumidor. Num canal público ele fica registrado.
- Regra: o selo só aparece quando o histórico daquele item cobre 90 dias. Antes disso, o texto não leva selo; um "menor preço desde DD/MM" fica para o frontend decidir no site.
- Isso também vale para o card do site, que hoje mostra o selo só com `price <= lowest_90d`. Ver a etapa 1.

**12.4 LGPD**
- Os canais não guardam dado de seguidor.
- O único dado pessoal novo é o `chat_id` do Elias, que fica em Secret e é removido apagando o Secret.
- Se um dia houver grupo (Manda Boa), ver a condição 5 da seção 9.

**12.5 Operação e custo**
- **Custo:** R$ 0. A Bot API do Telegram e o Canal do WhatsApp são grátis. O Manda Boa custaria R$ 69,90/mês, só se o gatilho disparar.
- **Tempo do Elias:** com até 5 ofertas por dia, a estimativa é de 5 a 10 min/dia, além dos ~10 min da Amazon. É o custo real.
- **Ban do WhatsApp:** com postagem manual pelo app oficial, o risco fica perto de zero. Ele só aparece com automação não oficial, o que a decisão 3 proíbe.
- **Volume:**
  - Com poucas ofertas elegíveis no começo, o canal pode passar dias sem post. Isso é aceitável pela curadoria, mas um canal mudo perde seguidor.
  - Acompanhar nas primeiras 2 semanas. Se ficar mudo, baixar o limiar de desconto (decisão 3), sem afrouxar o frescor.
- **Atraso do cron:** o GitHub atrasa minutos no pico, e uma oferta relâmpago do ML pode acabar antes do post. Isso é aceitável.

## 13. Decisões em aberto para o Elias

1. **Política da Amazon:** confirmar no Operating Agreement da Amazon.com.br:
   - que link de afiliado em canal público de Telegram e de WhatsApp é permitido;
   - e se é exigido aviso em cada post.

   Isso bloqueia o lançamento da parte Amazon dos canais.
2. **Medição do ML por canal:** aceitar os cliques do ML agregados no MVP (recomendado)? Ou gerar no painel três links por item (site, tg, wa) e guardar `ml_url_tg`/`ml_url_wa` no catálogo? A segunda opção triplica o trabalho manual de cada item do ML. Vale também conferir se o painel do ML oferece outro jeito de etiquetar a origem.
3. **Limiar de elegibilidade:** 30% de desconto ou selo de 90 dias é um bom começo? E os limites de 8 posts por dia no Telegram e 5 no resumo do WhatsApp?
4. **Foto da Amazon antes da Creators API:** usar a capa do Open Library por ISBN (exige ISBN no catálogo e mais uma fonte externa a validar), ou sair sem foto até a API (recomendado, por ser mais simples)?
5. **Nomes:** o `@username` do canal do Telegram, o nome do Canal do WhatsApp e quem é o administrador do Canal. Recomendo o número do Elias com um segundo administrador de backup, sem nenhuma automação nesse número.
6. **Horário do resumo do WhatsApp:** 11h BRT serve, ou outro horário combina melhor com a conferência da Amazon e com o público (por exemplo, 12h ou 19h)?

## Respostas do Elias (2026-10-18)
1. Política da Amazon para canal público: **em aberto, continua bloqueando a parte Amazon nos canais.**
2. Link por item: **o link vai para a loja com o menor preço**, e a outra loja fica numa seta ao lado. O contrato está em `comparacao-lojas.md`. Cliques do ML por canal: números agregados no MVP.
3. Limiar e limites (30% ou selo, 8 posts por dia no Telegram, 5 no resumo do WhatsApp): **talvez**. Ficam como constantes fáceis de ajustar, com esses valores iniciais.
4. Foto: ML com a foto do produto vinda da API. Amazon sem foto até a Creators API, quando passa a usar a imagem que ela devolver. Sem Open Library.
5. Bot do Telegram: `@ofertaslivros_bot`.
6. Horário do resumo do WhatsApp: em teste. Começa às 11h BRT, configurável.
