# Anúncios: rodada 1 (Instagram, Meta Ads)

Status: proposta do `brand-designer`, de 2026-11-07, aguardando a validação do Elias.
O destino do anúncio é a vitrine `/vitrine/` (cópia da home, noindex; ver docs/produto/anuncios-lancamento.md). O Telegram fica como secundário e não aparece na arte.

## Peças

| Arquivo (PNG + HTML) | Mensagem | Formato |
|---|---|---|
| `a-historico-feed-1080x1350` | A, histórico | Feed 4:5 |
| `a-historico-stories-1080x1920` | A, histórico | Stories e Reels 9:16 |
| `b-curadoria-feed-1080x1350` | B, curadoria | Feed 4:5 |
| `b-curadoria-stories-1080x1920` | B, curadoria | Stories e Reels 9:16 |

Nos Stories, todo o conteúdo fica entre y = 270 e y = 1630, com 250 px livres no topo e na base.

## Textos para o Ads Manager

O texto principal fica dentro de 125 caracteres e o título dentro de 40. O aviso de afiliado vai no texto principal (Amazon, Requisitos 6(l)).

### Peça A, histórico (feed e Stories)
- **Arte:** "Baixou de verdade?" + "A gente guarda o histórico de preço dos livros. Você vê se o desconto é real." + gráfico (sem valores) com o selo "Menor preço do histórico".
- **Texto principal** (110 car.): `Antes de comprar, veja o histórico de preço do livro e saiba se o desconto é real. Site com links de afiliado.`
- **Título** (31 car.): `Veja se o desconto é de verdade`
- **CTA:** Saiba mais
- **Variação de texto principal para teste** (116 car.): `Desconto inventado não passa: as ofertas mostram o histórico de preço do livro. Ganhamos comissão, sem custo a mais.`

### Peça B, curadoria (feed e Stories)
- **Arte:** "Só oferta verificada, todo dia." + "Livros que baixaram de preço, conferidos na loja e escolhidos a dedo." + três livros desenhados pela marca e o carimbo "conferido hoje".
- **Texto principal** (113 car.): `Ofertas de livros conferidas todo dia: só entra livro que baixou de preço de verdade. Site com links de afiliado.`
- **Título** (27 car.): `Ofertas de livros, todo dia`
- **CTA:** Ver ofertas
- **Variação de texto principal para teste** (119 car.): `Romance, mangá, negócios e mais: a gente confere o preço e só mostra o que baixou. Ganhamos comissão, sem custo a mais.`

## Marca e regras
- **Marca:** paleta do tema escuro do site (`static/style.css` na `origin/main`), Fraunces 800 com SOFT 100 e WONK 1 nos títulos, Outfit no texto, grão de papel, logo `logo-negativo.svg` (cópia do `static/`). O selo e o carimbo são os componentes do site em escala de anúncio, e os livros seguem a §11.1 da `spec-visual.md` (capa com miolo e fita na cor do nicho).
- **Fora da arte:** nome, logo ou cor das lojas; preço; capa real ou imagem de produto (as capas são blocos abstratos, sem título nem autor); urgência ou "mais vendido".
- **Pouco texto:** título + uma frase por peça, sem CTA desenhado. O botão é o do Meta.

## Contraste (WCAG, calculado)

Para o fundo tingido, o pior caso usado foi a mancha a 30%. O texto, na prática, fica em uma região mais escura que essa.

| Par | Cores | Razão | Mínimo |
|---|---|---|---|
| Título sobre o fundo | #e6ebf3 / #0f1729 | 14,93:1 | 4,5 |
| Título sobre o fundo tingido A | #e6ebf3 / #573a48 | 8,34:1 | 4,5 |
| Frase sobre o fundo | #a9b4c8 / #0f1729 | 8,55:1 | 4,5 |
| Frase sobre o fundo tingido A | #a9b4c8 / #573a48 | 4,78:1 | 4,5 |
| Frase sobre o fundo tingido B | #a9b4c8 / #372f66 | 5,71:1 | 4,5 |
| Selo: texto sobre o rosado | #0f1729 / #ff8a8f | 7,90:1 | 4,5 |
| Rótulos do gráfico sobre o painel | #a9b4c8 / #18233b | 7,49:1 | 4,5 |
| Linha do preço sobre o painel | #e6ebf3 / #18233b | 13,07:1 | 3 |
| Tracejado e ponto sobre o painel | #ff8a8f / #18233b | 6,92:1 | 3 |
| Carimbo sobre o fundo | #ff8a8f / #0f1729 | 7,90:1 | 3 (texto grande) |

## Como editar e renderizar
Edite o HTML ou o `anuncio.css` e rode `./render.sh`, que usa o Chrome da máquina em modo headless. As fontes vêm de `static/fonts/`, pelo caminho relativo.
