# Comparação Amazon × Mercado Livre por livro

Decisão do Elias (2026-10-18): cada livro mostra **um** botão principal que leva para a loja com o menor preço. Ao lado do botão fica uma seta pequena que abre o link da outra loja.

Este arquivo é o **contrato entre back e front**. O back (`collector-engineer`) gera `data/offers.json` neste formato, e o front (`build.py`) só lê. Mudanças no contrato passam por aqui primeiro.

## Contrato `data/offers.json` (v2)

Uma oferta passa a ser um **livro**, não um anúncio de uma loja.

```json
{
  "version": 2,
  "offers": [
    {
      "id": "habitos-atomicos",
      "isbn": "9788550807560",
      "genre": "negocios",
      "title": "Hábitos Atômicos",
      "author": "James Clear",
      "image_url": "https://http2.mlstatic.com/D_...jpg",
      "stores": [
        {"store": "amazon", "asin": "B0EXEMPL01",
         "price_cents": 3490, "list_price_cents": 6490,
         "lowest_90d_cents": 3490, "history_since": "2026-07-01",
         "checked_at": "2026-10-18T08:52:00-03:00"},
        {"store": "mercadolivre", "ml_product_id": "MLB19698440", "ml_url": "https://www.mercadolivre.com.br/social/...",
         "price_cents": 3290, "list_price_cents": 5990,
         "lowest_90d_cents": 3290, "history_since": "2026-10-18",
         "checked_at": "2026-10-18T09:10:00-03:00"}
      ]
    }
  ]
}
```

- `stores` tem 1 ou 2 itens, no máximo um por loja. Livro com uma loja só aparece com o botão e sem a seta.
- `image_url` é opcional. Por enquanto só vem do Mercado Livre (campo `pictures` da API de itens/produtos). A foto da Amazon só entra quando a Creators API for liberada: nada de tirar a foto da página da Amazon. Sem foto, o card usa um placeholder do nicho (gradiente e a inicial do título), sem fingir ser capa.
- O mesmo livro nas duas lojas é casado **pelo ISBN** no `collector/catalog.json`, que também passa a ter uma entrada por livro com os ids das duas lojas. Quando a API do ML devolver o GTIN, o coletor confere se bate com o ISBN; se não bater, descarta o preço do ML daquele livro e registra no log.

## Regras (o build aplica; o back não decide quem ganha)
1. **Loja elegível:** preço verificado dentro do prazo de frescor (ML até 2 h, Amazon até 12 h, conforme `distribuicao-canais.md`). Loja com preço velho não entra na comparação. Se nenhuma loja for elegível, o livro sai da lista.
2. **Vencedora:** a loja elegível com o menor `price_cents`. Em caso de empate, ganha a verificada mais recentemente.
3. **Selo "menor preço em 90 dias":** só aparece quando o preço da vencedora é ≤ o `lowest_90d_cents` de **todas** as lojas e quando há ao menos 90 dias de histórico (`history_since`). Sem 90 dias de histórico, o selo não aparece.
4. **Desconto exibido:** calculado sobre o `list_price_cents` da loja vencedora.
5. **Oferta x novidade** (decisão do Elias, 2026-10-19; limiar em `build.py:OFERTA_MIN_DESCONTO`):
   - **Oferta** é o livro cuja vencedora tem desconto ≥ **10%** sobre o próprio `list_price_cents`, **ou** o selo válido "menor preço em 90 dias" (regra 3).
   - O selo "menor preço desde DD/MM" (histórico com menos de 90 dias) **não** torna o livro oferta. Ele continua visível no card como informação.
   - Todo o resto é **novidade**: continua no site, mas nunca é chamado de oferta.
   - **Origem:** os primeiros livros do curator chegaram com 0% de desconto. O Elias decidiu mostrá-los num bloco "Novidades", sem o rótulo de oferta, para não contradizer a promessa do site ("só entra livro que baixou de preço de verdade"). O limiar de 10% foi o padrão proposto e aceito. Mudar o valor é mudar este contrato.
   - **Efeito na vitrine:**
     - As ofertas ocupam o hero/carrossel, "Destaques", "Ofertas ativas", o ranking e `/ofertas/`.
     - O hero completa com novidades marcadas como NOVIDADE quando há menos de 5 ofertas (ofertas primeiro; sem desconto nem riscado no slide de novidade).
     - As novidades ficam na seção "Novidades" da home, em `/novidades/` e na seção de novidades das páginas de nicho.
     - O card de novidade não tem sticker de desconto, preço riscado nem a palavra "oferta". Mantém o botão da loja e o alerta "Me avise se baixar".
     - `/livro/<id>/` existe para os dois.
     - Sem nenhuma oferta, a home mostra o aviso de estado vazio e só as novidades.
   - **Efeito na contagem:** "N ofertas" (header, filtros e seções) conta só as ofertas.
   - **Efeito nos canais:** `post_text` recusa novidade. O canal do Telegram e o resumo do WhatsApp (`distribuicao-canais.md`) só recebem ofertas. Os critérios de elegibilidade dos canais, como os 30% e o frescor, valem por cima desta regra.
   - **Alertas:** a regra não afeta os alertas individuais (`alerta-de-preco.md`). Novidade também pode ter alerta.

## Rotas (`_redirects`, todas estáticas e geradas no build)
- `/r/<id>`: vai para a loja vencedora.
- `/r/<id>/amazon` e `/r/<id>/mercadolivre`: vão para uma loja específica. É o link da seta.
- `/r/<id>/tg` e `/r/<id>/wa`: vão para a vencedora (posts dos canais).
- Todo destino passa por `affiliate_url` + `check_url` (allowlist de domínios).

## Front
- Botão principal: "Ver na Amazon por R$ 34,90" ou "Ver no Mercado Livre por R$ 32,90", conforme a vencedora.
- Seta ao lado: `<details>`/`<summary>` nativo, sem JS. Ela abre "Também no Mercado Livre: R$ 34,90" com o link `/r/<id>/<outra-loja>`. É acessível por teclado e tem um rótulo claro para leitor de tela.
- Cada loja mostra o próprio "verificado às HH:MM".
- CSP: incluir `https://http2.mlstatic.com` em `img-src`.

## Canais
- O post do Telegram e o resumo do WhatsApp mostram o preço da vencedora e o link `/r/<id>/tg` ou `/wa`. Se a outra loja estiver até 10% mais cara, o post diz "também no <loja> por R$ X", sem link extra.
