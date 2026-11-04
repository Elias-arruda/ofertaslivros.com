# Spec: links do ML pelo navegador do Elias

Rascunho do PM, 2026-11-04. Muda a regra 2 do CLAUDE.md e o passo 2 da §10.4 de `curadoria-automatica.md`. Segue o modelo da exceção da Amazon (#43, #50, §10.9).

## Problema

Hoje nenhum livro novo ganha `ml_url` sem o Elias abrir o Gerador de links, colar a `product_url` e devolver o link na `collector/ml_links.tsv`. Esse é o gargalo da curadoria: os livros ficam com `"pendente": true` e não saem pelo ML. O Elias quer tirar essa etapa manual. A agent `catalog-curator` passa a gerar o link pelo Chrome dele, aplicar com `links-apply` e abrir o PR.

## Escopo do MVP

1. **Exceção da regra 2**, nos moldes da regra 1:
   - **Onde:** só o Chrome do Elias (Claude in Chrome), já logado no portal de afiliados, e só no **Gerador de links oficial** do portal. Nada de barra/extensão de terceiros, Busqy ou `meli.la`.
   - **Ritmo:** uma página por vez, em ritmo humano, com cerca de 20 s entre ações (colar, gerar, copiar, abrir). Nada roda em paralelo nem em segundo plano.
   - **Lote:** até **20 links por dia** (`ML_LINKS_DAY = 20`), contando só livros novos com `ml_url` pendente. São uns 25 min por lote. O gate 8 permite até 50 candidatos por dia; o que passar de 20 fica para o dia seguinte.
   - **Proibido:** guardar cookie, token ou sessão; chamar API interna do portal; fazer `fetch`/`requests`/`curl` em código para o portal ou para o link gerado; rodar no GitHub Actions. O código do repo continua sem nenhuma request ao portal.
   - **Risco aceito pelo Elias:** a aceitação é o "aprovado, pode seguir" dele na sessão para o PR que cria esta exceção (2026-11-04). Sem esse merge, nada deste fluxo roda. Os termos do programa e o item 7.6 dos Termos de Desenvolvedores proíbem robôs no site. A punição possível é suspender a conta de afiliado e reter comissões.
2. **Validação de cada link** antes de ir ao TSV (ver abaixo).
3. **PR não sensível** quando só preenche `ml_url` pendentes (critérios abaixo).
4. **Parada segura** em captcha, verificação ou logout.

**Fora do MVP:**
- livro já publicado com `ml_url` (troca com `--replace`): continua manual e sensível;
- gerar mais de uma URL por vez no gerador;
- rodar sem o Elias com o computador ligado;
- script que confere o diff para o Codex (fazer só se o Codex errar a classificação).

## Fluxo (rodada sob demanda ou agendada na máquina do Elias)

1. `curator links-todo` gera a `collector/ml_links.tsv` (já existe). A agent pega até 20 linhas com `ml_url` vazio, só de livros com `"pendente": true` ou sem `ml_url`.
2. Para cada linha: ela abre o Gerador de links, cola a `product_url` (`https://www.mercadolivre.com.br/p/<MLB>`, montada pelo código), gera o link e copia o link completo `/social/...`.
3. Ela abre o link gerado uma vez, na mesma aba, e lê na barra de endereço o `/p/MLB…` ou o `MLB` do anúncio de destino. Depois espera uns 20 s.
4. Ela valida o link (seção seguinte). Se passar, cola o link na coluna `ml_url` da mesma linha. Se não passar, deixa a linha vazia e anota o motivo.
5. `curator links-apply collector/ml_links.tsv`, **sem `--replace`**.
6. Abre o PR no branch `Elias-arruda/ml-links-AAAA-MM-DD`. A descrição traz a saída do `links-apply` e, para cada livro, o `book_id`, o MLB esperado e o MLB visto no passo 3. Depois vem o review do Codex e o merge pelo fluxo de "PR e merge".

## Validação de cada link

O livro só entra se tudo bater. Se algo divergir, a linha fica vazia, o livro continua pendente e o motivo vai para a descrição do PR.

- **Conta e etiqueta:** passa no `ml_url()` do `build.py`, que o `links-apply` já chama via `affiliate_url`. Nada é afrouxado: o caminho é `/social/<ML_AFFILIATE_ID>`, o `matt_word` é o `ML_AFFILIATE_ID` ou uma etiqueta de `ML_LABELS`, as chaves estão em allowlist e aparecem uma vez só, o link é só ASCII e tem até 1000 caracteres, e `meli.la` é recusado. O `links-apply` também exige que o `ref` exista e não se repita no arquivo nem no catálogo.
- **Produto certo:** o MLB visto no passo 3 é igual ao `ml_product_id` da linha, que é igual ao do livro no `catalog.json`. Também vale o MLB do anúncio quando o `/p/` redireciona para um item do mesmo produto: a agent confere no título da página. Na dúvida, o livro fica pendente.
- **Barreiras que já existem:** o `links-apply` confere o `book_id` × `ml_product_id` e recusa livro que já tem `ml_url`. O `catalog-check` (CI, com `ML_AFFILIATE_ID: elias-arruda`) e o `build.py` validam tudo de novo.

O passo 3 substitui, neste fluxo, o GET com leitura do `og:title` que o `affiliate-linker` faz hoje (§10.4, item 5). Esse passo conta um clique da própria conta por link (ver decisão 3).

## Quando o PR deixa de ser sensível

Hoje todo PR que toca `ml_url` é sensível. Proposta: o PR deste fluxo **não é sensível** quando o Codex confirma **todos** os itens abaixo no `git diff origin/main...HEAD`:

1. Só mudam `collector/catalog.json` e `collector/ml_links.tsv`.
2. Nenhum livro entra nem sai do catálogo. O número de objetos em `books` é o mesmo, e a ordem e os `id` também.
3. Em cada livro alterado, a única mudança é esta: sai `"pendente": true` (quando existia) e entra `"ml_url"`. Nenhuma outra chave muda (título, autor, `genre`, `isbn`, `asin`, `ml_product_id`, tags).
4. Nenhuma linha removida do `catalog.json` tem `"ml_url"`, ou seja, nenhum `ml_url` existente muda ou some.
5. Todo `ml_url` novo começa com `https://www.mercadolivre.com.br/social/<id>?`, com o mesmo `<id>` dos `ml_url` que já estão na `origin/main`. O `matt_word` é esse `<id>` ou `ofertaslivros`.
6. São até 20 `ml_url` novos.
7. A descrição do PR lista, para cada livro, o MLB esperado e o MLB visto, iguais um ao outro.
8. O check `catalog-check` está verde.

Se qualquer item falhar, o PR é sensível e espera o "aprovado, pode seguir" do Elias. Um caso fica sensível por definição: o livro só da Amazon que ganha `ml_product_id` junto com o `ml_url` (§10.9, passo 5), porque a escolha do MLB é uma decisão de curadoria, não um preenchimento (ver decisão 4).

A mudança na lista de sensíveis do CLAUDE.md e na regra 2 é, ela mesma, um PR sensível.

## Riscos

- **Termos do ML:** os Termos de Desenvolvedores (7.6) proíbem robôs e scraping do site, e o programa de afiliados manda usar as ferramentas do portal. Operar o portal com um agente é acesso automatizado, mesmo no navegador real e em ritmo humano. O risco é suspender a conta e perder as comissões. Mitigações: lote pequeno, ritmo humano, só o gerador oficial, nada de sessão fora do Chrome.
- **Captcha, verificação, 2FA ou sessão expirada:** a agent **para o lote na hora**. Ela não tenta de novo, não resolve captcha e não faz login. As linhas restantes ficam vazias (pendentes), ela aplica e abre o PR só com o que já foi validado e avisa o Elias na sessão. Uma rodada nova só depois que o Elias liberar.
- **Clique próprio:** abrir o link gerado conta um clique da nossa conta. São no máximo 20 por dia, sem compra. Ainda assim, isso pode parecer tráfego inflado.
- **Regra 1 intacta:** nada aqui toca a Amazon.
- **Custo:** zero de infra. O custo é uns 25 min de Chrome e da sessão do Claude por dia.
- **LGPD:** não há dado de usuário.

## Quem faz o quê (na ordem)

1. **catalog-curator (docs):** atualiza a regra 2 do CLAUDE.md com a exceção, a §10.4 (o passo 2 aponta para esta spec) e o item de `ml_url` na lista de sensíveis, com os critérios acima. Também atualiza o próprio `.claude/agents/catalog-curator.md` (dona do fluxo) e o `affiliate-linker.md` (fica só para links colados pelo Elias). Esse PR é sensível.
2. **collector-engineer:** cria `ML_LINKS_DAY = 20` no `curator.py`. O `links-todo --max` ou o `links-apply` recusa mais de 20 linhas preenchidas por rodada, com um teste. É o único código novo.
3. **catalog-curator:** roda o primeiro lote real com 5 livros, acompanhado pelo Elias.
4. **security-auditor:** confere que nenhum código novo faz request ao portal ou ao `mercadolivre.com.br/social`, e que a validação do `ml_url` não foi afrouxada.
5. **code-reviewer (Codex):** aplica os critérios de sensível no primeiro PR de lote. O resultado dele é comparado com a classificação esperada.

## Critérios de aceite

- [ ] A regra 2 do CLAUDE.md descreve a exceção (só o Chrome do Elias, só o gerador oficial, cerca de 20 s, 20 por dia, sem sessão/API/requests) e o risco aceito, com a data.
- [ ] `git grep` não acha request a `mercadolivre.com.br/social` ou ao portal de afiliados em código. O `build.py` e o `ml_url()` não mudam.
- [ ] Com 21 linhas preenchidas, o `links-apply` aplica no máximo 20 (ou recusa), e há um teste.
- [ ] Num lote de teste, um link com `matt_word` de outra conta e um link cujo destino é outro MLB ficam pendentes, e os válidos entram.
- [ ] Captcha ou logout simulado (o Elias desloga no meio) para o lote: as linhas restantes ficam vazias, sai o aviso na sessão e não há nova tentativa.
- [ ] Um PR de lote que segue os critérios recebe do Codex "não sensível" e é mergeado sozinho. Um PR que também muda um `ml_url` existente ou outra chave é marcado como sensível.

## Decisões em aberto para o Elias

1. **Lote:** 20 links por dia está bom? Com 50, fecha o gate 8, mas expõe mais a conta. Até decidir, vale 20 (CLAUDE.md, regra 2).
2. **Conferência do MLB:** abrir o link gerado (gasta 1 clique próprio por link, recomendado) ou confiar só no par construído (colei a URL X e o gerador devolveu o link Y) e no título que o gerador mostra, sem clique?
3. **Livro só da Amazon:** o PR que adiciona `ml_product_id` e `ml_url` a esses livros fica sensível (recomendado) ou entra na regra de não sensível?
4. **Agenda:** sob demanda ou num horário fixo junto da rodada de preço das 8h53? Agendado, depende do computador e do Chrome ligados, como na Amazon.
