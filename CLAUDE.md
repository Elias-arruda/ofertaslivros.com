# Projeto: Site de ofertas de livros (afiliados Amazon + Mercado Livre)

Leia este arquivo inteiro antes de qualquer tarefa. Ele é o contexto do projeto.

## Objetivo
Site de ofertas de livros com links de afiliado da Amazon e do Mercado Livre.
Referência de produto: https://ofertasdiscos.com (vitrine curada + canais WhatsApp/Telegram + bot de alertas).
Domínio comprado na HostGator. A HostGator é usada SÓ para o domínio (DNS).

## Decisões tomadas
- **Curadoria, não despejo.** O site mostra ofertas ativas e verificadas. Oferta vencida sai da lista.
- **Diferencial:** histórico de preço ("menor preço em 90 dias"), que sites genéricos não mostram.
- **Arquitetura:**
  - Coletor em Python rodando em GitHub Actions (cron), gravando o histórico de preços em SQLite (ou Supabase, se precisar).
  - O coletor gera `data/offers.json`, e um site estático (Astro ou HTML puro) é gerado a partir dele.
  - Deploy no Cloudflare Workers (static assets, plano Free), que é o caminho que a Cloudflare indica para projetos novos no lugar do Pages. `_headers` e `_redirects` funcionam igual.
  - DNS: trocar os nameservers do domínio no painel da HostGator para os da Cloudflare. A HostGator fica só como registrador; não contratar hospedagem lá.
- **Fase 2:** canal no Telegram alimentado pelo mesmo pipeline. Depois, um bot com lista de desejos.

## Regras inegociáveis
1. **NUNCA fazer scraping da Amazon.** Isso viola os termos do programa de Associados e leva a banimento.
   - Amazon: usar a **Creators API**. A PA-API foi descontinuada em 2026.
   - Até a API ser liberada para a conta, o fluxo é semi-automático: o coletor monitora uma lista de ASIN/ISBN e um humano aprova e gera o link.
2. **Mercado Livre:** o preço vem da API pública de itens. O link de afiliado é gerado no painel de afiliados, salvo se houver um caminho oficial documentado.
3. **Credenciais:** chaves ficam só em GitHub Secrets ou `.env` local, que está no `.gitignore`. Nunca no código, nunca em JSON público.
4. **Transparência:** o rodapé deve ter o aviso de associado ("ganhamos com compras qualificadas") e dizer que o preço final é o da loja.

## Riscos de segurança específicos (ver /threat-model)
- **Open redirect** na rota de redirecionamento de afiliado (`/r/<id>`): só redirecionar para IDs conhecidos no `offers.json` e domínios em allowlist (amazon.com.br, mercadolivre.com.br, mercadolivre.com).
- **XSS** vindo de dados coletados (título, autor, descrição): sempre escapar o HTML e nunca usar `innerHTML` com dado externo.
- **Headers:** definir CSP, X-Content-Type-Options, Referrer-Policy e Permissions-Policy via `_headers` do Cloudflare.
- **Supply chain:** fixar versões de dependências e de actions do GitHub (por SHA). Revisar qualquer skill/agent de terceiros antes de instalar.

## Status (respondido em 2026-10-18)
- Aprovado nos Associados da Amazon e nos afiliados do ML.
- Creators API **ainda não liberada**: exige vendas qualificadas (≈10 em 30 dias) com a tag. Até lá vale o fluxo semi-automático.
- Livros em geral, com filtro por nicho: o campo `genre` usa o conjunto fechado `GENRES` do `build.py` e gera uma página por nicho (`/manga/` etc.).
- Link do ML: usar o link completo do painel (`www.mercadolivre.com.br/social/<id>?matt_word=<id>...`). O build confere o `matt_word` contra `ML_AFFILIATE_ID`. O `meli.la` não é aceito porque o build não consegue verificar de quem é a conta.

## Como trabalhar neste repo
- Elias é profissional de dados (Python, SQL, dbt, Airflow). Pode ser técnico, sem explicar o básico de Python.
- Comunicação em português, direta, com plano claro antes de executar.
- Pedido novo ou ambíguo: começar pelo `product-manager`, que escreve a spec em `docs/produto/` e diz qual agent implementa cada parte.
- Subagents em `.claude/agents/`, um por área:
  | Área | Agent | Skills |
  |---|---|---|
  | Produto | product-manager | — |
  | Front/UI | frontend-developer | frontend-design, web-design-guidelines |
  | Dados/coletor | collector-engineer | owasp-security |
  | Alertas/Telegram | alerts-engineer | owasp-security |
  | Segurança | security-auditor | owasp-security |
  | Revisão | code-reviewer | web-design-guidelines (quando o diff toca UI) |
- Antes de qualquer deploy: rodar `/security-review` e o subagent `security-auditor`.
