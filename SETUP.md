# Setup do kit Claude Code

## 1. Copiar para o repo
Descompacte na raiz do repositório do projeto. A estrutura fica assim:

```
CLAUDE.md                  # contexto e decisões do projeto (lido em toda sessão)
.claude/settings.json      # bloqueia leitura de .env e ativa o hook de segredos
.claude/hooks/secret_scan.py
.claude/agents/            # frontend-developer, collector-engineer, security-auditor, code-reviewer
.claude/commands/threat-model.md   # /threat-model
.gitignore
.env.example
```

Commite tudo, exceto o `.env`. Assim qualquer sessão (Claude Code puro, Orca ou outra) já abre com o contexto.

## 2. Skills de terceiros (instale manualmente, depois de ler o SKILL.md)
Não deixei isso automático de propósito: uma skill é um prompt com acesso ao terminal.

```bash
# Design (oficial Anthropic)
npx skills add https://github.com/anthropics/skills --skill frontend-design

# Auditoria de UI (Vercel)
npx skills add https://github.com/vercel-labs/agent-skills --skill web-design-guidelines

# OWASP (Top 10:2025, ASVS 5.0)
npx degit agamm/claude-code-owasp/.claude/skills/owasp-security .claude/skills/owasp-security
```

Antes de cada um: abra o repo no GitHub, leia o SKILL.md e veja se ele roda scripts.

## 3. Uso no dia a dia
- "use o collector-engineer para criar o coletor do Mercado Livre"
- "use o frontend-developer para montar a home com dados de exemplo"
- `/threat-model` uma vez agora, e de novo antes do primeiro deploy
- Antes de cada deploy: `/security-review` (nativo) e depois "rode o security-auditor"

## 4. Testar o hook
Peça ao Claude para escrever `API_KEY = "abcdefghijklmnop1234"` num arquivo .py. A escrita deve ser bloqueada.

## 5. Curator (docs/produto/curator.md), setup único
1. Settings > Actions > General: ligar "Allow GitHub Actions to create and approve pull requests" (o `gh pr create` do curator precisa).
2. Settings > Rules: ruleset na `main` exigindo PR e o check `catalog-check`. É isso que impede o `contents: write` do curator de chegar na `main`.
3. Conferir no painel de afiliados do ML, logado: termos sobre editar link e automação, se o Gerador aceita várias URLs, e se site, Telegram e WhatsApp estão declarados como canais. Fazer antes do primeiro merge de candidatos.
4. Actions > curator > Run workflow com `mode=probe`. Se `/highlights` der 200, rodar com `mode=suggest`.

## 6. Bot do Telegram (docs/produto/bot-lista-de-desejos.md)
- O `TELEGRAM_BOT_TOKEN` existe em **dois lugares**: no Environment `telegram` do GitHub (canal, `telegram.yml`) e nos segredos do Worker `ofertaslivros` (bot). Na rotação do token (BotFather, `/revoke`), atualize os dois:
  ```
  gh secret set TELEGRAM_BOT_TOKEN --env telegram
  npx wrangler@4.151.1 secret put TELEGRAM_BOT_TOKEN
  ```
- O `TELEGRAM_WEBHOOK_SECRET` só existe no Worker e no `setWebhook`. Para trocar, rode de novo o lançamento (abaixo), que gera um novo.
- Lançamento ou troca de token (depois do deploy do Worker com o bot). Copie o token no @BotFather (`/mybots` → bot → API Token) e rode na pasta do repo. O token sai da área de transferência (`pbpaste`), sem aparecer na tela nem no `ps`; o segredo do webhook é gerado na hora e também não aparece. No fim, a área de transferência é limpa.
  1. Conferir o token (tamanho 46 e `"ok":true`). Em 2026-11-06, colar no `read -rs` deu token vazio e o Telegram respondeu 404:
     ```
     TG=$(pbpaste | tr -d '[:space:]'); echo "tamanho: ${#TG}"; curl -sS -K <(printf 'url = "https://api.telegram.org/bot%s/getMe"\n' "$TG"); echo
     ```
  2. Na mesma janela do terminal, gravar os segredos no Worker e registrar o webhook (resposta esperada: `"Webhook was set"`):
     ```
     S=$(openssl rand -hex 32) && printf %s "$S" | npx wrangler@4.151.1 secret put TELEGRAM_WEBHOOK_SECRET \
       && printf %s "$TG" | npx wrangler@4.151.1 secret put TELEGRAM_BOT_TOKEN \
       && curl -sS -K <(printf 'url = "https://api.telegram.org/bot%s/setWebhook"\n' "$TG") -H 'Content-Type: application/json' \
          --data @<(printf '{"url":"https://ofertaslivros.com.br/telegram","secret_token":"%s","allowed_updates":["message","callback_query","my_chat_member"],"drop_pending_updates":true}' "$S"); echo; unset TG S; pbcopy </dev/null
     ```
  3. Se o token mudou, atualizar também o do canal: `gh secret set TELEGRAM_BOT_TOKEN --env telegram`.

## 7. Instagram (@ofertaslivros.com.br), post diário pela API oficial
Só a API oficial da Meta (Instagram API com login do Instagram, Content Publishing). Nada de instagrapi nem robô no navegador: dá ban.
O deploy gera o JPEG do post do dia em `/ig/` (`instagram_post.py --render`); o `instagram.yml` roda depois do deploy e publica.

- **Cadastro (uma vez):**
  1. No app da Meta (developers.facebook.com, portfólio "ofertaslivros.com.br"), produto **Instagram > API setup with Instagram login**, com as permissões `instagram_business_basic` e `instagram_business_content_publish`. A conta @ofertaslivros.com.br precisa ter papel no app (dona ou testadora): para publicar na própria conta não precisa de App Review.
  2. Em "Generate access tokens", adicionar a conta e gerar o token (já é o de longa duração, 60 dias). Guardar o token no gerenciador de senhas (a renovação usa ele) e anotar o **ID da conta** que aparece ao lado (só números).
  3. **Antes** de gravar o secret, criar o Environment no GitHub: Settings > Environments > New environment `instagram`, com "Deployment branches" = **Selected branches: `main`**. Conferir (a resposta não pode ser `null`):
     ```
     gh api repos/Elias-arruda/ofertaslivros.com/environments/instagram --jq .deployment_branch_policy
     ```
     Só então gravar o token e o ID dentro dele:
     ```
     pbpaste | tr -d '[:space:]' | gh secret set INSTAGRAM_TOKEN --env instagram; pbcopy </dev/null
     gh variable set INSTAGRAM_USER_ID --env instagram --body '<id numérico da conta>'
     ```
  Sem os dois, o job sai com `::warning::` e não posta.

- **Renovação do token (a cada ~50 dias; vence em 60).** O token precisa ter mais de 24 h e ainda estar válido. Copie o token atual (do gerenciador de senhas) e rode; ele sai da área de transferência, sem aparecer na tela nem no `ps`, o novo vai direto para o secret e fica na área de transferência para você guardar no gerenciador de senhas (é ele que a próxima renovação usa):
  ```
  IG=$(pbpaste | tr -d '[:space:]')
  NEW=$(curl -sS -K <(printf 'url = "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=%s"\n' "$IG") \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["access_token"], end=""); print("expira em", d["expires_in"] // 86400, "dias", file=sys.stderr)') \
    && [ -n "$NEW" ] && printf %s "$NEW" | gh secret set INSTAGRAM_TOKEN --env instagram \
    && printf %s "$NEW" | pbcopy; unset IG NEW
  ```
  Se o token venceu, gere outro no painel (passo 2). Vale um lembrete no calendário a cada 50 dias.

- **Renovação automática: não ligada, decisão do Elias.** O `GITHUB_TOKEN` não grava secrets. Automatizar exige um PAT fine-grained (ou um GitHub App) só deste repo, com escrita em Secrets/Environments, guardado no Environment `instagram`, e um workflow mensal que chama o `refresh_access_token` e grava o novo com `gh secret set` (sem imprimir o token). O custo: um token que pode trocar secrets do repo fica no Actions. Sem ele, a renovação é o comando acima.
