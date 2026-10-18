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
