---
description: Threat model do site de ofertas (STRIDE leve), focado nos ativos reais do projeto
---

Faça um threat model do estado atual do repositório. Leia o CLAUDE.md e a estrutura do repo primeiro.

Ativos a considerar:
- Credenciais da Creators API (Amazon) e do Mercado Livre
- Tag/ID de afiliado (sequestro = comissão desviada)
- `data/offers.json` e o histórico SQLite (integridade dos preços exibidos)
- Domínio e DNS na HostGator, e a conta do Cloudflare
- Futuro bot/canal do Telegram (token do bot)

Para cada fluxo de dados (coleta → JSON → build → deploy → clique do usuário → redirect → loja):
1. Liste as ameaças (Spoofing, Tampering, Repudiation, Information disclosure, DoS, Elevation).
2. Diga qual mitigação já existe no código (com arquivo:linha) ou se ela falta.
3. Priorize as 5 ações de maior impacto e menor esforço.

Inclua explicitamente: takeover de DNS/conta HostGator (ative 2FA), troca maliciosa da tag de afiliado no JSON, open redirect em /r/, e vazamento de segredo em log do Actions.

$ARGUMENTS
