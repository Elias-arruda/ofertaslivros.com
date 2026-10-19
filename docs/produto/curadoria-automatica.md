# Spec em rascunho: curadoria automática de livros

Status: rascunho para continuar com Elias e Claude. Atualizado em 2026-10-18.
Implementação bloqueada até definir o provedor autorizado de links de afiliado do Mercado Livre e aprovar os pesos/limiares da pontuação.

## 1. Objetivo confirmado

Criar um agente que, diariamente, descubra livros e ofertas, avalie o potencial de curadoria e publique automaticamente no site os livros aprovados pelas regras. Ao longo do dia, o sistema também deve acompanhar mudanças de preço nas ofertas publicadas e atualizar ou retirar ofertas desatualizadas.

Elias confirmou que o agente pode publicar sem aprovação humana por livro, desde que passe pelas regras automáticas.

## 2. Sinais de avaliação pedidos por Elias

- Preço em promoção em relação ao histórico real de preço.
- Número de compras recentes, considerando o período desde a publicação do livro.
- Número de avaliações.
- Interesse de busca do livro no Google Trends.

## 3. Proposta inicial de pontuação (ainda não aprovada)

Pontuar de 0 a 100 e guardar os componentes, dados de origem, instante de coleta e confiança. Pesos sugeridos para discussão:

| Componente | Peso | Regra candidata |
|---|---:|---|
| Preço/histórico | 35 | Comparar preço atual à mediana e ao mínimo observados nos últimos 90 dias. Sem histórico suficiente, não afirmar que é promoção; atribuir no máximo pontuação neutra/baixa. |
| Compras recentes ajustadas à idade | 25 | A API pode expor `sold_quantity` acumulado; guardar snapshots e estimar a variação em 30 dias. Comparar o ritmo com livros da mesma faixa de idade editorial. |
| Avaliações | 15 | Combinar quantidade e nota média, reduzindo a confiança de amostras pequenas. |
| Google Trends | 25 | Medir crescimento recente do interesse pelo título e autor, em vez de comparar índices absolutos de livros diferentes. |

Limiar candidato: publicar com pontuação >=70, desde que todos os gates da seção 4 passem. Limite, pesos, janelas e faixas precisam ser calibrados e aprovados antes da implementação.

## 4. Gates de publicação automática

Um candidato só pode ser publicado quando:

1. A identidade do livro/edição tiver correspondência forte, preferencialmente ISBN exato. Não misturar capa dura, brochura, edição revisada, box ou idioma diferente.
2. A oferta estiver ativa, com preço válido e consultado dentro do prazo máximo de frescor definido.
3. O link de afiliado for gerado por um provedor autorizado e validado pelas regras existentes do site.
4. O candidato não duplicar um livro/edição já publicado.
5. A pontuação e a confiança atingirem os limiares aprovados.

Falha em gate essencial bloqueia a publicação, mesmo com pontuação alta. Falha ou indisponibilidade de uma fonte de sinal deve ser registrada como dado ausente, nunca interpretada automaticamente como zero nem substituída por scraping não autorizado.

## 5. Descoberta, atualização e retirada

- **Descoberta diária:** buscar livros e ofertas em APIs/fontes autorizadas; normalizar por ISBN e edição; calcular e registrar a pontuação; publicar candidatos que passem nos gates.
- **Monitoramento intradiário:** revisitar ofertas publicadas várias vezes ao dia. O intervalo deve respeitar limites do provedor e ser configurável. Aumentar a frequência só para ofertas com variação recente ou grande interesse.
- **Preço no site:** informar horário da última consulta. Não apresentar preço velho como atual. Após erro repetido, indisponibilidade, link inválido ou oferta encerrada, despublicar ou marcar indisponível segundo prazo aprovado.
- **Histórico:** manter snapshots de preço para detectar queda real e não depender do rótulo promocional da loja.
- **Auditoria:** registrar por que o agente publicou, atualizou ou retirou cada oferta, com valores dos componentes e referências às fontes.

## 6. Geração de links Mercado Livre: descoberta e pendência principal

Busca feita em 2026-10-18:

- Não foi encontrada API pública oficial do Mercado Livre, documentada para criação de links de afiliado.
- A documentação oficial pública indica o Gerador de Links e a Barra de Afiliados. Também orienta que afiliados usem as ferramentas de criação do programa para divulgar links.
- Foi encontrado um caminho de terceiros: o Busqy documenta conversão automática usando uma conta colaboradora, uma extensão Busqy Tools que obtém um token no perfil de afiliado, e uma etiqueta. O artigo diz que o token da conta colaboradora precisa ser renovado mensalmente.
- Isso comprova que o Busqy oferece conversão dentro do próprio serviço; não comprova que tenha API pública para nosso backend, nem que o Mercado Livre tenha autorizado esse token para uso independente pelo nosso sistema.
- Não automatizar o portal do afiliado, não extrair cookies/sessões e não chamar endpoints privados descobertos por engenharia reversa.

### Verificações necessárias antes de escolher o provedor

1. Perguntar ao Busqy se existe endpoint/API contratual para converter URL do produto em link afiliado, utilizável pelo backend do ofertaslivros.com; pedir documentação, autenticação, limites, preço, SLA, política de retenção do token e procedimento de revogação.
2. Confirmar com o Mercado Livre se o fluxo do Busqy/token de colaborador está autorizado para conversão automatizada e publicação em site próprio.
3. Confirmar a renovação mensal do token, escopo mínimo da conta colaboradora e impacto de expiração/revogação.
4. Se qualquer resposta for negativa ou não houver interface contratual, manter geração de links manual até o programa oferecer método oficialmente autorizado. O agente pode continuar descobrindo e pontuando, mas não publica oferta sem link válido.

Fontes consultadas:

- [Mercado Livre: gerar links de afiliado](https://www.mercadolivre.com.br/l/afiliados-gere-seus-links)
- [Mercado Livre: direcionamento de visitas e links](https://www.mercadolivre.com.br/l/afiliados-direcionamento-de-visitas)
- [Busqy: token de autenticação do Mercado Livre](https://ajuda.busqy.app/pt-br/article/mercado-livre-como-gerar-o-token-de-autenticacao-n05jrz/)
- [Busqy: configuração dos programas de afiliado](https://ajuda.busqy.app/pt-br/article/como-configurar-os-programas-de-afiliado-shopee-amazon-etc-111nwhn/)

## 7. Fontes de dados e limitações já identificadas

- Mercado Livre: a API pública de itens permite consulta de anúncios e preço; `sold_quantity` é acumulado. Para estimar compras recentes, o sistema precisa salvar snapshots próprios. A API de avaliações documenta total e avaliações, sujeita a disponibilidade para o item/produto.
- Google Trends: a API oficial encontrada está em alpha e requer acesso. Os dados são normalizados; usar crescimento temporal do mesmo termo, não ranking direto entre títulos. Sem acesso, esse sinal fica ausente e a pontuação deve ser recalculada com confiança reduzida; não usar scraping de Trends como dependência obrigatória.
- Amazon: nunca fazer scraping. Descoberta, preços e links automatizados só podem usar a Creators API quando habilitada para a conta. Até lá, manter o fluxo manual/semi-automático já definido em `CLAUDE.md`.
- Catálogos como Google Books/Open Library podem ajudar a descobrir metadados, mas não substituem a confirmação de edição/oferta nem são sinal de preço ou vendas.

## 8. Próximas decisões para Claude/Elias

1. Confirmar com Busqy e Mercado Livre o método contratual de conversão e uso em site próprio.
2. Decidir se o lançamento começa só com Mercado Livre ou espera também a Creators API da Amazon.
3. Aprovar ou ajustar pesos, limiar de publicação, confiança mínima, histórico mínimo de preço e idade do preço.
4. Definir frequência intradiária, quantidade máxima de novos livros/dia, regras de retirada e política para fontes indisponíveis.
5. Quando esses pontos estiverem definidos, atualizar `docs/produto/alerta-de-preco.md` seção 11 e a spec de comparação de lojas, sem alterar o contrato `data/offers.json` sem atualizar a documentação correspondente.

## 9. Estado técnico relacionado ao handoff anterior

- PR #2 foi merged (`fa914b18daac60cb3f5a186090ca30da6b4297c8`), com paginação na consulta de itens do ML e limite de segurança.
- PR #1 continua aberto, limpo, base `main`: https://github.com/Elias-arruda/ofertaslivros.com/pull/1
- PR #3 continua aberto como draft, base PR #1, com workflow de deploy para Workers Static Assets: https://github.com/Elias-arruda/ofertaslivros.com/pull/3
- O deploy não foi executado. A revisão de segurança no HEAD `82cbb61` não achou bloqueios; `pip-audit` ficou limpo após atualizar pytest para 9.0.3.
- O worktree `hind` está no commit `ecfd277` e limpo antes deste handoff. O trabalho de PRs está nos worktrees `collector-pr2-pagination`, `front-reconcile` e `deploy-workflow`.
