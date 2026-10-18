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
  - Deploy no Cloudflare Pages. O DNS da HostGator aponta para o Cloudflare.
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
- **Headers:** definir CSP, X-Content-Type-Options, Referrer-Policy e Permissions-Policy via `_headers` do Cloudflare Pages.
- **Supply chain:** fixar versões de dependências e de actions do GitHub (por SHA). Revisar qualquer skill/agent de terceiros antes de instalar.

## Pendências (perguntar ao Elias se ainda estiverem em aberto)
- Já é aprovado nos Associados da Amazon e no programa de afiliados do ML? A Creators API está liberada?
- Recorte de nicho (ficção, negócios, mangá, técnicos...) ou livros em geral? A recomendação é começar com um recorte.

## Como trabalhar neste repo
- Elias é profissional de dados (Python, SQL, dbt, Airflow). Pode ser técnico, sem explicar o básico de Python.
- Comunicação em português, direta, com plano claro antes de executar.
- Subagents em `.claude/agents/`: frontend-developer, collector-engineer, security-auditor, code-reviewer.
- Antes de qualquer deploy: rodar `/security-review` e o subagent `security-auditor`.
