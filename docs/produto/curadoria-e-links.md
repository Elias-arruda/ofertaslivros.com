# Curadoria de livros de todas as áreas e link de afiliado do ML

Status: pesquisa (entrega 1 do `catalog-curator`), 2026-10-19. Nada foi implementado.
Este doc **complementa** `curadoria-automatica.md` §10, não o substitui: gêneros, pontuação, gates, modo sombra e o fluxo de links em lote continuam lá. **Em caso de conflito, prevalece `curadoria-automatica.md` §10** (com a precedência da §10.8 de lá). Aqui ficam as fontes com o que os termos de cada uma permitem, os critérios de entrada e saída, os 100 candidatos iniciais e a pesquisa do link do ML.

Convenção (a mesma de §10): **Fato** tem fonte e data. **Inferência** é dedução minha, a confirmar. **Não confirmado** é o que tentei e não consegui verificar. Todas as fontes foram acessadas em **2026-10-19**.

---

## Parte A. Curadoria

### A.1 Fontes: o que cada uma permite

| Fonte | Para quê | O que os termos permitem | Status |
|---|---|---|---|
| **API pública do ML** (`/categories`, `/highlights`, `/trends`, `/products`, `/reviews`) | Descoberta (mais vendidos e tendências da categoria `MLB437616`), preço, GTIN, gênero (`BOOK_GENRE`) | [Termos do Programa de Desenvolvedores](https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes). **Fato**, li o texto: 5.2 manda tirar do site o conteúdo que deixar de estar disponível. 5.3 manda atualizar a cada 24 h, e a cada **6 h** quando o conteúdo é listagem de artigos, e diz que "o Aplicativo deverá explicitar a frequência com que atualiza". 5.4 exige **autorização expressa** do ML para usar ou publicar o conteúdo de um jeito que gere estatística de vendas (5.4.3), preço médio ou volume vendido por categoria (5.4.4) e taxas de conversão (5.4.6). 7.6 proíbe robôs e scraping do site ou dos serviços. 7.8 proíbe volume abusivo | Em produção para preço. As rotas de descoberta ainda estão no passo 0 de §10.2 |
| **Amazon Creators API** | Descoberta (busca, browse nodes), preço, ASIN, avaliações | É o único caminho permitido para a Amazon (CLAUDE.md, regra 1). O acesso exige cerca de 10 vendas qualificadas em 30 dias ([Creators API, Introduction](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction), citada em `22548f4`) | **Indisponível** para a conta. Até lá, o ASIN entra à mão |
| **Open Library** | Metadados por ISBN (título, editora, data), checagem de ISBN | [Developers API](https://openlibrary.org/developers/api). **Fato:** o limite é de 1 req/s sem identificação e de 3 req/s com `User-Agent` e e-mail. A página diz "Please do not use our APIs to bulk download metadata" (para volume, usar os dumps mensais) e proíbe "Use Open Library as a backend for high-traffic commercial services" | Usada nesta pesquisa (A.4). Só pode rodar na curadoria, com cache, e nunca no caminho de uma requisição do site. O e-mail do `User-Agent` deve ser um contato do projeto, não o pessoal |
| **Google Books API** | Metadados, `averageRating`/`ratingsCount` | [Terms](https://developers.google.com/books/terms). **Fato:** proíbe cobrar do usuário pelo uso da aplicação e obriga a remover conteúdo infrator quando pedido. Vale também o Google APIs ToS | **Fato:** a chamada anônima de hoje deu 429 com `quota_limit_value: "0"`. Sem chave própria, não há cota. Decidido: chave própria (decisão 9 de §10.6) |
| **Ranking Nielsen-PublishNews** | Sinal de demanda (mais vendidos do varejo físico brasileiro) | **Não confirmado:** não achei termos de uso nem política de reprodução. **Fato:** a página descreve a metodologia (BookScan da NielsenIQ, só livro físico, painel de 60% a 70% do mercado trade) ([exemplo de ranking](https://www.publishnews.com.br/ranking-nielsen/anual/5/2025/2/0)). O dado é da Nielsen | **Só entrada manual.** Nada de coleta automática nem republicar a lista ou os números. No máximo, o Elias anota "constou no ranking de <mês>" como sinal interno |
| **Lista da Veja** | Idem | **Não confirmado:** não verifiquei de onde vem a lista nem os termos. Uma revista não é dado aberto | Só entrada manual, com o mesmo tratamento do PublishNews |
| **Prêmio Jabuti (CBL)** | Sinal editorial (premiados e finalistas) | É um fato público (quem ganhou), que a imprensa reproduz ([CNN Brasil, vencedores de 2025](https://www.cnnbrasil.com.br/pop/premio-jabuti-2025-confira-os-livros-vencedores-de-todas-as-categorias/); [PublishNews, finalistas de 2025](https://www.publishnews.com.br/materias/2025/10/07/chico-buarque-jeferson-tenorio-e-ruy-castro-sao-finalistas-do-premio-jabuti-2025-veja-a-lista-completa)). **Não confirmado:** não li o site oficial | Entrada manual uma vez por ano: um arquivo com título, autor e categoria, e o ISBN conferido pelo GTIN do ML. Serve de semente para `literatura-brasileira`, que o ML não mapeia (§10.1) |
| **Google Trends API** | Tendência | Ver §10.2 (alpha, acesso por formulário) | Sem acesso. Pedido decidido (decisão 8 de §10.6) |

**Proibido, sem exceção:**
- Scraping da Amazon, **incluindo as páginas de Mais Vendidos**, de busca e de produto, e a foto da capa tirada da página.
- Raspar HTML do ML (item 7.6), seguir a URL de busca que o `/trends` devolve, e chamar endpoint privado descoberto por engenharia reversa (7.5).
- `pytrends` ou scraping do Google Trends.
- Coleta automática de listas de terceiros sem termos que a permitam (PublishNews, Veja, Amazon e afins).

**Achado novo, que muda §10.3: cláusula 5.4 do ML.** Usar Δ`sold_quantity` para estimar "compras recentes" é, ao pé da letra, derivar estatística de vendas (5.4.3/5.4.4), e isso pede autorização expressa, que pode ser dada por e-mail.
- **Inferência:** usar a posição no `/highlights`, que é o ranking que o próprio ML publica pela API, dentro da pontuação e sem exibir, tem risco baixo.
- Mostrar no site "nº 3 no ML" ou "X vendidos" tem risco maior.
- Recomendação: pedir a autorização ao ML antes de ligar o componente Demanda com `sold_quantity` e não exibir posição nem volume de vendas no site (decisão B1 em §C).

**Achado novo para o front: cláusula 5.3.** O site precisa dizer com que frequência atualiza os preços do ML, por exemplo no rodapé: "Preços do Mercado Livre consultados a cada 30 min". O "verificado às HH:MM" de cada card ajuda, mas não diz a frequência. Isso fica com o `frontend-developer`.

### A.2 Critérios de entrada no catálogo

Catálogo é a lista monitorada (`collector/catalog.json`). Pela decisão A do Elias (`curadoria-automatica.md` §10.8), todo livro publicado com loja fresca aparece na área **Curadoria** (`/curadoria/`), com ou sem desconto; a **vitrine de ofertas** (home, páginas de nicho e canais) mostra só os que estão **em oferta**. Os gates de §4 e §10.3 continuam valendo. Abaixo, os critérios por livro, com o que bloqueia e o que só pontua.

| Critério | Regra | Tipo |
|---|---|---|
| ISBN válido | ISBN-13 com dígito verificador correto e prefixo 978 ou 979. O ISBN-10 é convertido. ~~Sem ISBN, o livro não entra~~ *Substituído pelo gate 7 reescrito (`curadoria-automatica.md` §10.3): o ISBN é opcional para livro só do ML, porque o `/products/{id}` não traz GTIN (probe 39259800320); presente, tem de ser válido* | Bloqueia se presente e inválido |
| Mesma edição nas duas lojas | Gate 7 da rodada 3 (`curadoria-automatica.md` §10.3): identidade por loja; o casamento é pelo ISBN-13 quando os dois lados têm, e, sem ISBN no ML, pelo `isbn_confirmado` que o Elias preenche na fila da Amazon (§10.5). A confirmação pelo `/products/search` foi rejeitada. Se não bater, o livro entra só com a loja que confere. **Nunca casar por título.** Capa dura, brochura, box, edição de colecionador e HQ adaptada têm ISBNs diferentes. Nesta pesquisa, por exemplo, o "1984" que a Open Library devolveu primeiro era a versão em quadrinhos (`9788535932522`), e não o romance (`9788535914849`) | Bloqueia |
| Formato | Livro físico: categoria `MLB437616` no ML e ASIN de livro físico na Amazon, não Kindle | Bloqueia |
| Idioma | Edição brasileira (prefixos `97885`/`97865`) como padrão. Importado, só por entrada manual | Bloqueia no automático |
| Disponibilidade | Item ativo na buy box ou em `/products/{id}/items`, condição **novo** e preço conferido dentro do frescor (2 h no ML, 12 h na Amazon) | Bloqueia |
| Vendedor no ML | Reputação verde. **Não confirmado:** terceiros dizem que o link de afiliado só vale para "produtos novos de vendedores com reputação verde" (resumo do resultado de busca sobre a [página do programa](https://www.mercadolivre.com.br/l/afiliados-home)). O campo é `seller_reputation.level_id` de `GET /users/{seller_id}`, a conferir no passo 0 | Bloqueia (se confirmado) |
| Desconto real | **Não bloqueia a entrada nem a publicação** (decisão A, `curadoria-automatica.md` §10.8). Decide só se o livro aparece como **oferta** na home, nas páginas de nicho e nos canais, pelo critério "em oferta" da §10.8: com menos de 30 dias de histórico nosso, "de/por" da loja com desconto ≥ 10%; com 30 dias ou mais, preço ≤ 85% da mediana dos dias 8 a 90 (anti-maquiagem: uma alta logo antes da "promoção" não infla o desconto) ou o selo de 90 dias. Sem oferta, o livro fica só na área Curadoria. No score em sombra, vale §10.3 | Pontua (sombra) e separa oferta de curadoria |
| Popularidade | Posição no `/highlights` (oficial), o bônus do `/trends` e as marcações manuais (PublishNews, Jabuti, Veja). Um sinal ausente não conta como zero | Pontua |
| Duas lojas | Livro com as duas lojas tem nota maior, porque alimenta a comparação. Hoje a Amazon é manual, então isso pesa pouco | Pontua |
| Equilíbrio de gêneros | No máximo M novos livros por gênero por dia (gate 8) | Bloqueia o excedente |
| Edição em catálogo na editora | **Inferência:** a melhor prova é ter item novo ativo no ML. A Open Library não diz se a edição ainda é vendida | Coberto pela disponibilidade |
| Séries (mangá, HQ) | Cada volume tem ISBN próprio. Proposta: vol. 1 e o volume mais recente, para não lotar a vitrine com 100 volumes | Regra do curador |
| Domínio público | Clássicos como Machado e Orwell (morto em 1950, em domínio público no Brasil desde 2021) têm dezenas de edições. Fica a edição com GTIN no ML e o maior ranking. As outras não entram | Regra do curador |

### A.3 Critérios de saída

- **Da vitrine de ofertas** (o livro segue na área Curadoria): deixou de estar em oferta pelo critério da §10.8.
- **Do site** (o livro continua no catálogo): nenhuma loja elegível pelo frescor, item pausado ou encerrado e, só depois da calibração, `score < 60` por 2 execuções (§10.3). Isso também cumpre o item 5.2 do ML.
- **Do catálogo:** GTIN deixou de bater com o ISBN; link de afiliado inválido ou recusado no build; 30 dias sem nenhum item novo ativo em nenhuma loja (sinal de edição esgotada; é a leitura provisória do "30 dias sem oferta" de `curadoria-automatica.md` §10.7, decisão 4, e §10.8, item 6). ~~180 dias sem entrar na vitrine e sem sinal de demanda~~ *Substituído pela §10.8, item 6, que deixa em aberto a retirada por falta de oferta (`aba-curadoria.md` §14, decisão 1).* Retirada registrada com motivo e componentes (§5, auditoria).
- **O `id` nunca é reaproveitado**, mesmo depois da retirada (gate 9).

### A.4 Gêneros

O ponto de partida é o `GENRES` atual do `build.py`: `literatura-brasileira`, `ficcao`, `negocios`, `nao-ficcao`, `manga`.

Mantenho sem mudança a proposta de §10.1:
- entram `autoajuda`, `infantojuvenil`, `religiao`, `estudo` e `estilo-de-vida`;
- os 5 slugs atuais ficam como estão, porque já são URLs;
- `literatura-brasileira` é só manual.

Dois ajustes de rótulo, só como proposta, a decidir pelo `product-manager`:
- `estudo` → "Estudo, técnicos e concursos". Ressalva: Vade Mecum e apostila de concurso **não entram**, porque têm edição anual e o ISBN muda todo ano;
- `estilo-de-vida` → "Saúde, culinária e hobbies", um rótulo mais curto para o menu.

Não proponho mais gêneros. Com 10, cada nicho ainda pode ter oferta todo dia.

### A.5 Candidatos iniciais (10 por gênero)

Como verifiquei:
- Fonte: o registro de edição da Open Library, `https://openlibrary.org/isbn/<ISBN>.json` ou `/works/<id>/editions.json`, acessado em 2026-10-19.
- "Confirmado" quer dizer que a Open Library tem uma edição brasileira com esse ISBN-13, com dígito verificador válido e título batendo.
- "Confirmado" **não** quer dizer que a edição esteja em catálogo, nem que seja a edição vendida no ML ou na Amazon. Isso é o gate de GTIN que decide.
- Editora e ano são os que a Open Library registra. ⚠ marca uma edição provavelmente antiga ou um dado estranho da Open Library: confirmar o GTIN antes de usar.
- "A verificar" quer dizer que não achei o ISBN em fonte aberta. **Não chutei.** Dois palpites meus, testados, eram de outro livro (ver as notas).

**`ficcao`**

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | É Assim que Acaba | Colleen Hoover | 9788501112514 | Galera Record, 2018 | Confirmado |
| 2 | Verity | Colleen Hoover | 9786559815043 | Galera Record, 2024 | Confirmado. 1º no ranking Nielsen-PublishNews de abr/2026, segundo um trecho indexado (não abri a página) |
| 3 | Os Sete Maridos de Evelyn Hugo | Taylor Jenkins Reid | 9788584391509 | Paralela, 2019 | Confirmado |
| 4 | A Biblioteca da Meia-Noite | Matt Haig | 9786558380542 | Bertrand Brasil | Confirmado |
| 5 | 1984 | George Orwell | 9788535914849 | Companhia das Letras, 2009 | Confirmado. Não usar `9788535932522`, que é a HQ |
| 6 | A Revolução dos Bichos | George Orwell | 9786555790641 | PandorgA, 2020 | Confirmado. Está em domínio público e há muitas edições |
| 7 | Duna | Frank Herbert | 9788576574941 | Aleph | Confirmado |
| 8 | O Hobbit | J.R.R. Tolkien | 9788533615540 | WMF Martins Fontes | Confirmado ⚠ edição antiga. A atual é da HarperCollins Brasil e o ISBN está a verificar |
| 9 | A Paciente Silenciosa | Alex Michaelides | 9788501116437 | Record, 2019 | Confirmado |
| 10 | Quarta Asa | Rebecca Yarros | — | — | **A verificar** |

**`literatura-brasileira`** (só manual)

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | Torto Arado | Itamar Vieira Junior | 9786580309313 | Todavia | Confirmado |
| 2 | Tudo é Rio | Carla Madeira | 9786555871784 | Record, 2021 | Confirmado |
| 3 | Dom Casmurro | Machado de Assis | 9786586490084 | Antofágica, 2020 | Confirmado. Domínio público, muitas edições |
| 4 | Memórias Póstumas de Brás Cubas | Machado de Assis | — | — | **A verificar.** A OL tem `9786580210015` com "Nova Aguilar, 1994", o que é incoerente porque o prefixo 978-65 não existia em 1994, e `/isbn` não confirmou |
| 5 | A Hora da Estrela | Clarice Lispector | 9786555320350 | Rocco, 2020 | Confirmado |
| 6 | Vidas Secas | Graciliano Ramos | 9786580210886 | Antofágica, 2024 | Confirmado |
| 7 | Capitães da Areia | Jorge Amado | 9788535911695 | Companhia das Letras, 2008 | Confirmado |
| 8 | Grande Sertão: Veredas | Guimarães Rosa | 9788520918876 | Nova Fronteira, 2006 | Confirmado ⚠ edição antiga. Não usar `9786559210046`, que é a HQ |
| 9 | O Avesso da Pele | Jeferson Tenório | 9788535933390 | Companhia das Letras, 2020 | Confirmado |
| 10 | Quarto de Despejo | Carolina Maria de Jesus | 9788508196555 | Ática, 2021 | Confirmado |

**`negocios`**

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | Hábitos Atômicos | James Clear | 9788550807560 | Alta Books, 2019 | Confirmado |
| 2 | Pai Rico, Pai Pobre | Robert Kiyosaki | 9788550801483 | Alta Books, 2017 | Confirmado |
| 3 | A Psicologia Financeira | Morgan Housel | 9786555111101 | HarperCollins | Confirmado |
| 4 | O Homem Mais Rico da Babilônia | George S. Clason | 9788595081536 | HarperCollins, 2017 | Confirmado |
| 5 | O Investidor Inteligente | Benjamin Graham | 9788595080805 | HarperCollins, 2016 | Confirmado |
| 6 | Rápido e Devagar | Daniel Kahneman | 9788539003839 | Objetiva, 2012 | Confirmado |
| 7 | Essencialismo | Greg McKeown | 9788543102146 | Sextante, 2015 | Confirmado |
| 8 | Do Mil ao Milhão | Thiago Nigro | 9788595083271 | HarperCollins, 2018 | Confirmado |
| 9 | Comece pelo Porquê | Simon Sinek | 9788543106632 | Sextante, 2018 | Confirmado |
| 10 | A Startup Enxuta | Eric Ries | 9788581780047 | Lua de Papel, 2012 | Confirmado ⚠ edição antiga |

**`nao-ficcao`**

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | Sapiens | Yuval Noah Harari | 9788535933925 | Companhia das Letras, 2020 | Confirmado |
| 2 | Pequeno Manual Antirracista | Djamila Ribeiro | 9788535932874 | Companhia das Letras, 2019 | Confirmado. ⚠ A OL registra o título como "Autografado", e por isso o GTIN tem de ser conferido |
| 3 | O Diário de Anne Frank | Anne Frank | 9788501068200 | Record, 2014 | Confirmado. Muitas edições |
| 4 | Eu Sou Malala | Malala Yousafzai | 9788565765626 | Seguinte, 2015 | Confirmado ⚠ Seguinte é selo juvenil. Conferir se é a edição adulta |
| 5 | 1808 | Laurentino Gomes | 9788576653202 | Planeta, 2007 | Confirmado ⚠ edição antiga (hoje sai pela Globo Livros) |
| 6 | Escravidão, vol. 1 | Laurentino Gomes | 9786580634019 | "Buobooks" na OL | Confirmado ⚠ a editora registrada é estranha. Conferir o GTIN |
| 7 | Uma Breve História do Tempo | Stephen Hawking | 9788580576467 | Intrínseca, 2015 | Confirmado |
| 8 | Steve Jobs | Walter Isaacson | 9788563560902 | Companhia das Letras, 2014 | Confirmado |
| 9 | Minha História | Michelle Obama | 9788547000646 | Objetiva, 2018 | Confirmado |
| 10 | Nexus | Yuval Noah Harari | — | — | **A verificar** |

**`manga`**

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | One Piece, vol. 1 | Eiichiro Oda | — | — | **A verificar.** A OL só tem o vol. 3 |
| 2 | Jujutsu Kaisen, vol. 1 | Gege Akutami | — | — | **A verificar.** A OL só tem o vol. 8 (`9786559820863`) |
| 3 | Chainsaw Man, vol. 1 | Tatsuki Fujimoto | 9786555127331 | Panini | Confirmado |
| 4 | Demon Slayer, vol. 1 | Koyoharu Gotouge | — | — | **A verificar** |
| 5 | Spy x Family, vol. 1 | Tatsuya Endo | — | — | **A verificar** |
| 6 | Berserk, vol. 1 | Kentaro Miura | — | — | **A verificar** |
| 7 | Attack on Titan, vol. 1 | Hajime Isayama | — | — | **A verificar** |
| 8 | Maus | Art Spiegelman | 9788535906288 | Companhia das Letras, 2005 | Confirmado |
| 9 | Watchmen | Alan Moore e Dave Gibbons | 9786525933351 | Panini | Confirmado |
| 10 | Turma da Mônica: Laços | Vitor e Lu Cafaggi | — | — | **A verificar** |

**`autoajuda`** (novo)

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | A Sutil Arte de Ligar o F*da-se | Mark Manson | 9788551002490 | Intrínseca, 2017 | Confirmado |
| 2 | Mais Esperto que o Diabo | Napoleon Hill | 9788568014004 | Citadel, 2014 | Confirmado |
| 3 | Como Fazer Amigos e Influenciar Pessoas | Dale Carnegie | 9788543108681 | Sextante, 2019 | Confirmado. Existe também `9788504018028` (Cia. Editora Nacional, 2012), que é outra edição |
| 4 | Mindset | Carol S. Dweck | 9788547000240 | Objetiva, 2017 | Confirmado |
| 5 | O Poder do Agora | Eckhart Tolle | — | — | **A verificar.** O meu palpite `9788575421437` é "Boa Sorte". Não usar |
| 6 | Inteligência Emocional | Daniel Goleman | — | — | **A verificar.** `9788573022254` é "Trabalhando com a Inteligência Emocional" |
| 7 | A Coragem de Ser Imperfeito | Brené Brown | 9788575429587 | Sextante, 2013 | Confirmado |
| 8 | Ansiedade: Como Enfrentar o Mal do Século | Augusto Cury | 9788502218482 | Saraiva, 2013 | Confirmado ⚠ edição antiga |
| 9 | O Milagre da Manhã | Hal Elrod | 9788576849940 | Best Seller, 2016 | Confirmado |
| 10 | O Poder do Hábito | Charles Duhigg | 9788539004256 | Objetiva | Confirmado |

**`infantojuvenil`** (novo)

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | O Pequeno Príncipe | Antoine de Saint-Exupéry | 9786559570737 | Prime, 2020 | Confirmado. Domínio público, muitas edições |
| 2 | Harry Potter e a Pedra Filosofal | J.K. Rowling | 9788532530783 | Rocco, 2017 | Confirmado |
| 3 | Diário de um Banana, vol. 1 | Jeff Kinney | 9788576831303 | V&R, 2008 | Confirmado |
| 4 | O Menino Maluquinho | Ziraldo | 9788506055106 | Melhoramentos, 2010 | Confirmado |
| 5 | A Culpa é das Estrelas | John Green | 9788580572261 | Intrínseca, 2012 | Confirmado |
| 6 | Percy Jackson e o Ladrão de Raios | Rick Riordan | 9788598078694 | Intrínseca, 2010 | Confirmado |
| 7 | Extraordinário | R.J. Palacio | 9788580573015 | Intrínseca, 2013 | Confirmado. Não confundir com "Somos Todos Extraordinários" (`9788551001622`) |
| 8 | Jogos Vorazes | Suzanne Collins | 9786555321449 | Rocco, 2021 | Confirmado |
| 9 | O Menino do Pijama Listrado | John Boyne | 9788535911121 | Seguinte, 2008 | Confirmado |
| 10 | A Bolsa Amarela | Lygia Bojunga | — | — | **A verificar.** A OL só tem a Agir de 1983, que não confirmou |

**`religiao`** (novo)

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | O Peregrino | John Bunyan | 9786559960415 | "Livrarias Família Cristã", 2021 | Confirmado. Muitas edições |
| 2 | Cartas de um Diabo a seu Aprendiz | C.S. Lewis | 9788578601843 | Thomas Nelson Brasil, 2019 | Confirmado |
| 3 | Cristianismo Puro e Simples | C.S. Lewis | 9788578601775 | Thomas Nelson Brasil, 2017 | Confirmado |
| 4 | O Livro dos Espíritos | Allan Kardec | 9788573287523 | FEB, 2019 | Confirmado |
| 5 | Nosso Lar | Chico Xavier (André Luiz) | 9788573289442 | FEB, 2019 | Confirmado |
| 6 | A Cabana | William P. Young | 9788599296363 | "Windblown Media" na OL | Confirmado ⚠ a editora brasileira não aparece. Conferir o GTIN |
| 7 | Uma Vida com Propósitos | Rick Warren | — | — | **A verificar** |
| 8 | Ansiosos por Nada | Max Lucado | — | — | **A verificar** |
| 9 | O Caibalion | Três Iniciados | — | — | **A verificar.** O meu palpite `9788531503030` é outro livro |
| 10 | Bíblia Sagrada (NVI) | — | — | — | **A verificar.** Há dezenas de ISBNs, um por capa e formato. Recomendo deixar fora do automático |

**`estudo`** (novo)

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | Código Limpo | Robert C. Martin | 9788576082675 | Alta Books | Confirmado |
| 2 | Arquitetura Limpa | Robert C. Martin | 9788550804606 | Alta Books, 2019 | Confirmado |
| 3 | Entendendo Algoritmos | Aditya Bhargava | 9788575225639 | Novatec, 2017 | Confirmado |
| 4 | Python Fluente | Luciano Ramalho | 9788575224625 | Novatec, 2015 | Confirmado ⚠ é a 1ª edição. A 2ª tem outro ISBN, a verificar |
| 5 | Introdução à Programação com Python | Nilo Ney Coutinho Menezes | — | — | **A verificar** |
| 6 | O Programador Pragmático | David Thomas e Andrew Hunt | — | — | **A verificar** |
| 7 | Moderna Gramática Portuguesa | Evanildo Bechara | — | — | **A verificar.** A OL só tem a Lucerna de 1999, que não confirmou |
| 8 | Pedagogia da Autonomia | Paulo Freire | 9786555480245 | (sem editora na OL), "Edição especial" | Confirmado ⚠ conferir a editora |
| 9 | Como se Faz uma Tese | Umberto Eco | 9788527300797 | (sem editora na OL) | Confirmado ⚠ conferir a editora |
| 10 | Estatística Básica | Wilton Bussab e Pedro Morettin | 9788547220228 | Saraiva Uni, 2017 | Confirmado |

**`estilo-de-vida`** (novo)

| # | Título | Autor | ISBN-13 | Editora (OL) | Verificação |
|---|---|---|---|---|---|
| 1 | Sal, Gordura, Ácido, Calor | Samin Nosrat | — | — | **A verificar** |
| 2 | Por que Nós Dormimos | Matthew Walker | — | — | **A verificar** |
| 3 | Ikigai | Héctor García e Francesc Miralles | — | — | **A verificar** |
| 4 | A Mágica da Arrumação | Marie Kondo | — | — | **A verificar.** `9788522006908` é a versão em quadrinhos |
| 5 | Roube como um Artista | Austin Kleon | 9788532528421 | Rocco, 2013 | Confirmado |
| 6 | A História da Arte | E.H. Gombrich | — | — | **A verificar.** `9788521611851` é outro livro |
| 7 | Nascido para Correr | Christopher McDougall | 9788525063793 | Globo Livros, 2016 | Confirmado |
| 8 | O Corpo Fala | Pierre Weil e Roland Tompakow | 9788532602084 | Vozes, 2002 | Confirmado |
| 9 | 1.000 Lugares para Conhecer Antes de Morrer | Patricia Schultz | — | — | **A verificar** |
| 10 | Cozinha Prática | Rita Lobo | — | — | **A verificar** |

**Resumo:**
- 73 ISBNs confirmados e 27 a verificar.
- Dos confirmados, 12 têm ⚠ de edição.
- Faltam mais ISBNs em mangá e estilo de vida (7 em cada): a Open Library cobre mal as traduções recentes e a Panini.
- O caminho para fechar os 27 era o GTIN do produto do ML, mas o passo 0 mostrou que a ficha não traz GTIN (§10.2); sobra a chave própria do Google Books (decisão 9 de §10.6). Scraping de loja ou de livraria, para isso, não.
- A seleção dos títulos é minha, a partir de presença conhecida no varejo, e não de um ranking medido, com exceção de Verity e A Biblioteca da Meia-Noite. O `/highlights` deve substituir essa escolha assim que o passo 0 rodar.

---

## Parte B. Link de afiliado do Mercado Livre

### B.1 O que está documentado oficialmente

- **Fato:** o portal de desenvolvedores não tem endpoint de afiliado. Os [Termos](https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes) não mencionam afiliados. A busca `site:developers.mercadolivre.com.br afiliados` não trouxe nenhuma página do portal. Isso confirma §6.
- **Fato, a partir das páginas oficiais do programa, lidas só pelo trecho indexado no buscador:** as páginas `/l/afiliados-*` e a [ajuda 39155](https://www.mercadolivre.com.br/ajuda/programa-afiliados-criadores_39155) pedem login ("Para continuar, acesse sua conta") ou devolvem 403. Não li o texto integral. Os trechos indexados dizem:
  - os links são criados pela **Barra de Afiliados**, na página do produto, ou pela **Central de Afiliados e Criadores**, onde dá para copiar o link ou o ID do produto ([Comece a recomendar](https://www.mercadolivre.com.br/l/comece-a-recomendar));
  - não se gera link para a home, a busca, as páginas de categoria nem o carrinho ([Gerar link](https://www.mercadolivre.com.br/l/afiliados-gerar-link));
  - **as páginas se contradizem sobre os canais.** [Pode compartilhar](https://www.mercadolivre.com.br/l/afiliados-pode-compartilhar) lista como **não permitidos**: "WhatsApp, Telegram, Buscadores, como Google e Bing, Mídia considerada off-line". [Onde compartilhar](https://www.mercadolivre.com.br/l/afiliados-onde-compartilhar) lista WhatsApp e Telegram como permitidos.
- **Não li** os Termos e Condições do Programa de Afiliados e Criadores no original. Eles ficam atrás do login.

### B.2 O que é só observado ou inferido

- **Observado:** o formato do link do painel, presente em `collector/catalog.json`, é `https://www.mercadolivre.com.br/social/<aff>?matt_word=<aff>&matt_tool=<n>&forceInApp=true&ref=<cifrado>`.
  - O `ref` é cifrado e **não contém o id do produto**.
  - Por isso nenhum script consegue saber, só pelo link, a que produto ele pertence (§10.4).
- **Inferido, não documentado:** montar à mão a URL do produto com `matt_word` e `matt_tool` (sem `ref`) atribuiria a comissão.
  - Ninguém oficial documenta isso.
  - Terceiros citam o item 1.8 dos termos do programa, que proíbe "corte, edição ou modificação dos Links Especiais" que esconda que o link leva ao domínio do ML ([grupodewhatsapp.com](https://grupodewhatsapp.com/blog/afiliado-mercado-livre-como-gerar-link), atualizado em 19/10/2026).
  - **Não montar.** O `build.py:ml_url` já rejeita esse formato, e deve continuar assim.
- **Terceiros, não confirmado:** o Gerador de links aceitaria "1 ou mais URLs, uma por linha" ([Canaltech](https://canaltech.com.br/internet/como-se-cadastrar-no-programa-de-afiliados-do-mercado-livre/)). Isso reduziria o trabalho do lote.
- **Terceiros:** o Busqy converte links com token de uma "conta colaboradora" (§6). Não há confirmação de que o ML autorize isso. Ferramentas como o CLI do [TabNews](https://www.tabnews.com.br/marcuth/criei-uma-cli-para-gerar-links-de-afiliados-de-marketplaces) usam cookie de sessão, o que é proibido aqui.

### B.3 O que não existe (até 2026-10-19)

- API oficial para gerar o link de afiliado.
- Padrão de URL documentado para o link de afiliado.
- API de relatório de cliques e comissões para afiliado.

Conclusão: **não há caminho oficial automático.** Vale o fluxo semi-automático em lote de §10.4, sem mudança de desenho:
- `links-todo` gera um TSV com `book_id`, `ml_product_id`, `product_url` montada pelo código e `ml_url` vazia;
- o Elias gera os links no painel e cola cada um na linha do seu `book_id`;
- `links-apply` valida cada linha com `affiliate_url` e `check_url` do `build.py` (`/social/<aff>`, `matt_word == ML_AFFILIATE_ID`, chaves em allowlist, sem `meli.la`) e rejeita `ref` duplicado e produto desconhecido;
- livro sem link válido não publica.

Ajuste barato, se o Gerador aceitar mesmo várias URLs:
- `links-todo` imprime também as `product_url` num bloco, para colar de uma vez no Gerador;
- o pareamento continua **por linha e pelo `book_id`**, nunca pela ordem da saída do Gerador, porque um erro de ordem não seria detectável (§10.4, item 4).

### B.4 Riscos com os termos

| Risco | Gravidade | Mitigação |
|---|---|---|
| **Telegram e WhatsApp podem estar proibidos** (página "Pode compartilhar") | **Alta para a Fase 2** (canal no Telegram) | O Elias confere no painel qual página vale, de preferência por escrito ao suporte do programa, **antes** de ligar o canal. Até lá, os posts de canal apontam só para a Amazon ou para a página do livro no site, não para `/r/<id>/tg` do ML |
| "Buscadores" na lista de não permitidos | Média | **Inferência:** deve ser anúncio pago em buscador. Não comprar anúncio com link do ML. SEO orgânico do site deve ser aceito ("site/blog" consta como permitido), mas é a confirmar |
| A rota `/r/<id>` esconde o domínio do ML (item 1.8, citado por terceiros) | Média | O botão já diz "Ver no Mercado Livre", e o destino é o link completo do painel, sem edição. Alternativa conservadora: no card, o `href` da loja ML aponta direto para o `ml_url` e `/r/` fica só para a Amazon e os canais. Decisão do `product-manager` |
| Automatizar o painel (Playwright, extensão, cookie) | Alta (banimento) | Proibido (CLAUDE.md, item 7.6 dos termos de dev) |
| Abrir o link de afiliado para "validar" | Média (clique falso, acesso ao site) | A validação é só sintática (`build.py`). Nunca fazer GET no `ml_url` |
| Link fora das regras (produto usado, vendedor sem reputação verde, página de busca ou categoria) | Média (comissão zerada) | Gates de condição e reputação (A.2), e `product_url` sempre `/p/<MLB>` |
| Usar `sold_quantity` para derivar vendas (item 5.4) | Média | Pedir autorização ao ML, ou usar só o `/highlights` (A.1) |
| Termos mudam sem aviso, e eu não li o original | Média | O Elias lê os Termos do programa logado e registra aqui a data e os itens sobre canais, edição de link e automação |
| Busqy sem confirmação contratual | Média | Fica fora até haver contrato e aval do ML (§6) |

---

## C. Decisões novas para o Elias (somam-se às de §10.6)

- **B1.** Pedir ao ML autorização por escrito (cláusula 5.4) para usar Δ`sold_quantity` na pontuação, ou desistir desse sinal e ficar só com o `/highlights`.
- **B2.** Conferir no painel se Telegram e WhatsApp são permitidos. Isso bloqueia o link do ML nos canais da Fase 2.
- **B3.** No card, a loja ML usa `href` direto para o `ml_url` (mais conservador quanto ao item 1.8) ou mantém `/r/<id>/mercadolivre`?
- **B4.** Aprovar os critérios de A.2, em especial o desconto mínimo (≤ 85% da mediana dos dias 8 a 90, ou ≤ o mínimo de 90 dias) e as séries (vol. 1 + o mais recente).
- **B5.** Bíblia e Vade Mecum ficam fora do automático?

### C.1 Decisões do Elias (2026-10-19)

- **B1.** O Δ`sold_quantity` sai da pontuação. A popularidade vem do `/highlights`. Em paralelo, pedir ao ML autorização por escrito (cláusula 5.4). Se vier, o sinal volta.
- **B2.** O link do ML **fica liberado** nos canais de Telegram e WhatsApp, seguindo a página "Onde compartilhar". O Elias aceitou o risco de a página "Pode compartilhar" valer. Se o painel ou o suporte disser o contrário, o canal passa a apontar para o site.
- **B3.** Mantém `/r/<id>/mercadolivre`. O destino continua sendo o link completo do painel, sem edição, e o botão diz "Ver no Mercado Livre".
- **B4.** Os critérios de A.2 foram aprovados como estão. *(O "Desconto real" foi revisto pela decisão A, `curadoria-automatica.md` §10.8: separa oferta de curadoria e não bloqueia a entrada.)*
- **B5.** Bíblia, Vade Mecum e apostilas de concurso ficam fora do automático e entram só manualmente.

## D. Próximos passos (nada executado)

| # | Passo | Agent |
|---|---|---|
| 1 | Consolidar `GENRES` e os rótulos de A.4 (B1–B5 já decididas em C.1) | `product-manager` |
| 2 | Ler os Termos do programa de afiliados no painel, logado, e registrar aqui os itens sobre canais, edição de link e automação | Elias (manual) |
| 3 | Rodar o passo 0 (`probe` só leitura com o token de app), incluindo `/users/{seller_id}` para reputação e `/products/search?product_identifier=<ISBN>` para os 27 ISBNs a verificar | `catalog-curator` |
| 4 | Fechar os ISBNs a verificar pelo GTIN do ML e corrigir as edições com ⚠ | `catalog-curator` |
| 5 | Implementar descoberta, casamento pelo gate 7, pontuação em sombra, gates e `links-todo`/`links-apply`, com pytest para casamento, gates e validação de link (entrega 2, depois da aprovação) | `catalog-curator` |
| 6 | Mostrar a frequência de atualização no rodapé (cláusula 5.3) | `frontend-developer` |
| 7 | ~~Bloquear o link do ML nos posts de Telegram e WhatsApp~~ Cancelado: a B2 liberou o link do ML nos canais | — |
| 8 | Revisar o fluxo de links em lote e o uso de dados de terceiros antes de ligar a publicação | `security-auditor` |
