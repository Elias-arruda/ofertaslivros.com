# Fontes auto-hospedadas

Baixadas em 2026-10-19 do registry do npm (pacotes do Fontsource com versão fixa). O `integrity` do tarball conferiu com o publicado no registry. Licença SIL OFL 1.1 nas duas (texto em `OFL-Fraunces.txt` e `OFL-Outfit.txt`, copiados do `LICENSE` de cada pacote).

| Arquivo | Pacote | Tarball | sha256 do woff2 | Eixos (lidos do `fvar`) |
|---|---|---|---|---|
| `fraunces-latin-full-normal.woff2` (121.016 B) | @fontsource-variable/fraunces 5.3.0 | https://registry.npmjs.org/@fontsource-variable/fraunces/-/fraunces-5.3.0.tgz | `7e744849028e2219e2aa1bc467dc4032980dc4487c9c3da3010081cd72d3b103` | opsz 9–144, wght 100–900, SOFT 0–100, WONK 0–1 |
| `fraunces-latin-full-italic.woff2` (149.720 B) | idem | idem | `04a14ea380db53a35a3ec651934b21061234685bb604d30aac82663b5d9e539b` | opsz 9–144, wght 100–900, SOFT 0–100, WONK 0–1 |
| `outfit-latin-wght-normal.woff2` (32.292 B) | @fontsource-variable/outfit 5.3.0 | https://registry.npmjs.org/@fontsource-variable/outfit/-/outfit-5.3.0.tgz | `6c18d579fd87c3776be068b762cbc83fde3acb543d49eabd3ade842eb987e887` | wght 100–900 |

Integridade dos tarballs (campo `dist.integrity` do registry):
- fraunces-5.3.0.tgz: `sha512-9BYGySn4AHEJdgp9Z28tQ3X+laJMEOITXkQarZXeloWQZDq5oOvXJ3kDA8c7MGIfpogIaZfjrQBqmda8POOCKA==`
- outfit-5.3.0.tgz: `sha512-fPb5XnYK0k7SbR++HEmm4+ZqDszmLKQ+sPRUr8oQ/KNC0vy6r6hazJFe8iYozv4cqlHbvJ/JECkJWrfDodUMVQ==`

Subconjunto *latin* (cobre os acentos do português). A Fraunces vem no arquivo `full`, o único do pacote com SOFT **e** WONK juntos (o `soft` não tem WONK e o `wonk` não tem SOFT). O custo é o peso: 121 KB no romano contra 37 KB do `wght`. Se o peso incomodar, a troca mais barata é o `soft` (62 KB), mas aí o WONK some.

Para reconferir: `shasum -a 256 static/fonts/*.woff2`.
