# Marca: decisões (2026-10-18)

Material do `brand-designer`. A pesquisa está em `pesquisa.md`, as paletas e o contraste em `paletas.md` e as técnicas de layout em `layout.md`. O `contraste.py` citado em `paletas.md` e as pranchetas (`*.dc.html`) ficaram fora do repo.

## Logo: "Carimbo de verificado"
Um círculo duplo girado -10° com um livro aberto, em vermelho `#b3262f`, e "Ofertas Livros" em serifa. Os SVGs estão em `logos/`:

| Arquivo | Uso |
|---|---|
| `carimbo-horizontal.svg` | topo do site (`static/logo.svg`) |
| `carimbo-negativo.svg` | rodapé escuro (`static/logo-negativo.svg`) |
| `carimbo-favicon.svg` | favicon 32 px (`static/favicon.svg`) |
| `carimbo-simbolo.svg` | símbolo solto (placeholder de capa) |
| `carimbo-empilhada.svg`, `carimbo-mono.svg` | avatar de canal e impressão |

O texto do logotipo usa a fonte do sistema (Iowan Old Style, Palatino...), então muda um pouco de aparelho para aparelho. Converter em curvas na rodada de refinamento.

## Paleta provisória: Ficha
A paleta atual do `static/style.css`: fundo `#e8ecf0`, ficha `#ffffff`, tinta `#1c2b4a`, texto secundário `#4a5670`, pauta `#b9cbe2` e vermelho `#b3262f`. O vermelho fica reservado ao selo, ao desconto e ao carimbo. A tipografia é a opção A (Charter + system-ui), sem fonte externa.

## Componentes aprovados (no site)
1. O selo "Menor preço em 90 dias" é uma pílula vermelha cheia, colada ao preço, e só aparece com 90 dias reais de histórico em todas as lojas elegíveis. "Menor preço desde DD/MM" usa contorno.
2. Gráfico do histórico: SVG inline gerado no build a partir de `price_points`, com o ponto vermelho no preço atual e a faixa por extenso ("90 dias: R$ X a R$ Y" ou "desde DD/MM: ...").
3. Preço legível (Baymard): preço grande e tabular, com o riscado e o desconto ao lado, mostrados uma vez só.
4. "Feito à mão": o carimbo do topo mostra "conferido DD/MM às HHhMM", com o horário da coleta mais recente. É só CSS.
5. Urgência honesta: "visto hoje às HHhMM" por loja e "caiu R$ X desde DD/MM" quando o histórico mostra a queda. Nada de contador.
6. "Emoção, depois decisão": uma frase curta do livro (`blurb`, opcional), seguida do preço.
7. Capas: a foto real do ML, quando houver, num quadro 2:3 neutro. Quando não há foto, um placeholder sóbrio com o carimbo, que não finge ser capa.

## Para a rodada de refinamento
- Logotipo em curvas e revisão do favicon em 16 px.
- Escala tipográfica fluida (Utopia 1,2 → 1,25) e um espaçamento único em tokens (`layout.md` §1 e §5).
- Container queries no card (`layout.md` §3) e o modo escuro (`paletas.md`).
- Avaliar a paleta final (Ficha, Marca-texto ou Joia) e a fonte OFL auto-hospedada (opção B).
- Regra do 100 do Baymard no desconto (% abaixo de R$ 100, valor em reais acima).
