/* Ofertas Livros: melhoria progressiva. Sem ele o site funciona igual (links reais, carrossel em CSS).
   Lê só o que o próprio HTML traz (data-* e o JSON de #ofertas) e escreve só com textContent,
   createElement e atributos conferidos. Nada de HTML vindo de string. */
(() => {
  'use strict';
  const d = document, root = d.documentElement;
  const $ = (s, el = d) => el.querySelector(s), $$ = (s, el = d) => [...el.querySelectorAll(s)];
  const show = el => { if (el) el.hidden = false; };
  const fold = s => s.toLowerCase().normalize('NFKD').replace(/\p{M}/gu, '').trim();
  root.classList.add('js');

  /* Tema: prefers-color-scheme por padrão; o botão grava a escolha */
  const tema = $('.js-tema');
  const isDark = () => root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  let saved = null;
  try { saved = localStorage.getItem('tema'); } catch (_) { /* modo privado */ }
  if (saved === 'dark' || saved === 'light') root.dataset.theme = saved;
  if (tema) {
    show(tema);
    const sync = () => tema.setAttribute('aria-pressed', String(isDark()));
    sync();
    tema.addEventListener('click', () => {
      const t = isDark() ? 'light' : 'dark';
      root.dataset.theme = t;
      try { localStorage.setItem('tema', t); } catch (_) { /* sem persistência */ }
      sync();
    });
  }

  /* Feed: busca, filtro de nicho, ordenação e "carregar mais" sobre os cards que já estão no HTML */
  const grid = $('.feed'), PAGE = 12;
  let render = null;
  if (grid) {
    const cards = $$(':scope > .card', grid), blocks = $$(':scope > .blk', grid);
    const full = grid.classList.contains('feed--full');
    const mais = $('.js-mais'), vazio = $('.vazio'), count = $('#h-ativas + .sec-n'), sel = $('#ordem');
    const st = { q: '', g: '', order: '', limit: PAGE };
    const keys = { preco: c => +c.dataset.preco, off: c => -c.dataset.off };
    $$('.mais a[href="/ofertas/"]').forEach(a => { a.parentNode.hidden = true; });
    show($('.feed-tools'));
    render = () => {
      let list = cards.slice();
      if (st.order === 'rec') list.sort((a, b) => (a.dataset.rec < b.dataset.rec) - (a.dataset.rec > b.dataset.rec));
      else if (keys[st.order]) list.sort((a, b) => keys[st.order](a) - keys[st.order](b));
      const hits = list.filter(c => (!st.g || c.dataset.g === st.g) && (!st.q || c.dataset.q.includes(st.q)));
      list.forEach(c => {
        grid.appendChild(c);
        const k = hits.indexOf(c);
        c.hidden = k < 0 || (!full && k >= st.limit);
      });
      // Os blocos voltam para a posição de origem, contada entre os cards visíveis
      const vis = hits.slice(0, full ? hits.length : st.limit);
      blocks.forEach(b => {
        b.hidden = Boolean(st.q || st.g);
        grid.insertBefore(b, vis[+b.dataset.at] || null);
      });
      if (mais) mais.hidden = full || hits.length <= st.limit;
      if (vazio) vazio.hidden = hits.length > 0;
      if (count) count.textContent = hits.length + ' no momento';
    };
    if (sel) sel.addEventListener('change', () => { st.order = sel.value; render(); });
    if (mais) mais.addEventListener('click', () => {
      const first = st.limit;
      st.limit += PAGE;
      render();
      const next = cards.filter(c => !c.hidden)[first];
      if (next) $('.card-title a', next).focus();
    });
    // Filtro sem recarregar: troca o acento global (data-style) e o nicho ativo
    const rail = $('.rail[data-filtro]');
    if (rail) rail.addEventListener('click', e => {
      const a = e.target.closest('a[data-f]');
      if (!a || e.ctrlKey || e.metaKey || e.shiftKey) return;
      e.preventDefault();
      st.g = a.dataset.f;
      st.limit = PAGE;
      if (st.g) root.dataset.style = st.g; else delete root.dataset.style;
      $$('a[data-f]', rail).forEach(x => (x === a ? x.setAttribute('aria-current', 'page') : x.removeAttribute('aria-current')));
      render();
    });
    const busca = $('#q');
    if (busca) busca.addEventListener('input', () => {
      st.q = fold(busca.value);
      st.limit = PAGE;
      render();
      const sec = $('#h-ativas');
      if (sec && sec.getBoundingClientRect().top > innerHeight * 0.6) sec.scrollIntoView({ block: 'start' });
    });
    render();
  }

  /* Busca no header: filtra o feed da página; sem feed, leva a /ofertas/?busca= */
  const bBtn = $('.js-busca'), faixa = $('#busca'), input = $('#q');
  if (bBtn && faixa && input) {
    show(bBtn);
    const abrir = on => {
      faixa.hidden = !on;
      bBtn.setAttribute('aria-expanded', String(on));
      if (on) input.focus();
    };
    bBtn.addEventListener('click', () => abrir(faixa.hidden));
    input.addEventListener('keydown', e => {
      if (e.key === 'Escape') { abrir(false); bBtn.focus(); }
      if (e.key === 'Enter' && !grid && input.value.trim()) location.href = '/ofertas/?busca=' + encodeURIComponent(input.value.trim());
    });
    const pedida = new URLSearchParams(location.search).get('busca');
    if (pedida && grid) { input.value = pedida.slice(0, 80); abrir(true); input.dispatchEvent(new Event('input')); }
  }

  /* Carrossel: setas, arraste, contador e barra; o tempo de cada slide é a animação da barra (CSS) */
  const hero = $('.hero');
  if (hero) {
    const track = $('.hero-track', hero), view = $('.hero-view', hero);
    const slides = $$('.slide', hero), segs = $$('.segs li', hero), n = slides.length;
    const cnt = $('.js-n', hero), pausar = $('#pausar');
    let i = 0, over = false, foco = false, x0 = null, dx = 0, moved = false;
    hero.classList.add('js');
    [$('.hero-count', hero), $('.js-prev', hero), $('.js-next', hero)].forEach(show);
    const pause = () => hero.classList.toggle('paused', over || foco || Boolean(pausar && pausar.checked));
    const go = k => {
      i = (k + n) % n;
      track.style.setProperty('--i', i);
      slides.forEach((s, j) => { s.inert = j !== i; });
      segs.forEach((li, j) => {
        li.classList.toggle('seen', j < i);
        li.classList.remove('on');
        if (j === i) { void li.offsetWidth; li.classList.add('on'); } // reinicia a barra
      });
      if (cnt) cnt.textContent = i + 1;
    };
    hero.addEventListener('animationend', e => { if (e.animationName === 'fill') go(i + 1); });
    hero.addEventListener('mouseenter', () => { over = true; pause(); });
    hero.addEventListener('mouseleave', () => { over = false; pause(); });
    hero.addEventListener('focusin', () => { foco = true; pause(); });
    hero.addEventListener('focusout', e => { if (!hero.contains(e.relatedTarget)) { foco = false; pause(); } });
    if (pausar) pausar.addEventListener('change', pause);
    $('.js-prev', hero).addEventListener('click', () => go(i - 1));
    $('.js-next', hero).addEventListener('click', () => go(i + 1));
    segs.forEach((li, j) => $('a', li).addEventListener('click', e => { e.preventDefault(); go(j); }));
    view.addEventListener('pointerdown', e => { if (e.button === 0) { x0 = e.clientX; dx = 0; moved = false; } });
    view.addEventListener('pointermove', e => {
      if (x0 === null) return;
      dx = e.clientX - x0;
      if (Math.abs(dx) > 8) { moved = true; hero.classList.add('drag'); track.style.setProperty('--dx', dx + 'px'); }
    });
    const solta = () => {
      if (x0 === null) return;
      x0 = null;
      hero.classList.remove('drag');
      track.style.setProperty('--dx', '0px');
      if (Math.abs(dx) > 50) go(i + (dx < 0 ? 1 : -1));
    };
    view.addEventListener('pointerup', solta);
    view.addEventListener('pointercancel', solta);
    view.addEventListener('click', e => { if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; } }, true);
    view.addEventListener('dragstart', e => e.preventDefault());
    go(0);
  }

  /* Modal de detalhes: o link é a página real /livro/<id>/; aqui ele abre num <dialog> e entra no histórico */
  const dlg = $('#detalhe'), dataEl = $('#ofertas');
  if (dlg && dataEl && typeof dlg.showModal === 'function') {
    let data = [];
    try { data = JSON.parse(dataEl.textContent); } catch (_) { data = []; }
    const byId = new Map(data.map(o => [o.id, o]));
    const OK = { r: /^\/r\/[a-z0-9-]+(\/(amazon|mercadolivre))?$/, pag: /^\/livro\/[a-z0-9-]+\/$/, tg: /^https:\/\/t\.me\/[A-Za-z0-9_]+\?start=[A-Za-z0-9_-]+$/ };
    let list = [], idx = 0, opener = null, porPop = false;
    const txt = (sel, v) => { const el = $(sel, dlg); el.textContent = v || ''; el.hidden = !v; return el; };
    const link = (href, text, cls, rel, sr) => {
      const a = d.createElement('a');
      a.href = href; a.className = cls; a.textContent = text;
      if (rel) { a.rel = rel; a.target = '_blank'; }
      if (sr) { const s = d.createElement('span'); s.className = 'sr'; s.textContent = sr; a.append(s); }
      return a;
    };
    const fill = o => {
      if (/^[a-z-]+$/.test(o.g)) { dlg.dataset.g = o.g; $('.m-gi', dlg).setAttribute('href', '#i-g-' + o.g); }
      txt('.m-g', o.gl); txt('.m-t', o.t); txt('.m-a', o.a);
      $('.m-nota', dlg).hidden = !o.blurb; txt('.m-blurb', o.blurb);
      $('.m-selo', dlg).hidden = !o.selo;
      const selo = $('.m-selo .stamp', dlg);
      selo.textContent = o.selo || ''; selo.classList.toggle('stamp--since', Boolean(o.desde));
      txt('.m-meta', o.meta); txt('.m-hist', o.hist); txt('.m-p', o.p); txt('.m-de', o.de);
      txt('.m-off', o.off ? '−' + o.off + '%' : '');
      const img = $('.m-img', dlg), ini = $('.m-ini', dlg), foto = typeof o.img === 'string' && o.img.startsWith('https://http2.mlstatic.com/');
      $('.m-obj .cover', dlg).classList.toggle('cover--none', !foto);
      img.hidden = !foto; ini.hidden = foto;
      if (foto) { img.src = o.img; img.alt = 'Capa de ' + o.t + ', de ' + o.a; } else { img.removeAttribute('src'); ini.textContent = o.t.charAt(0).toUpperCase(); }
      const acts = $('.m-acts', dlg);
      acts.replaceChildren();
      (o.lojas || []).forEach(l => {
        if (!OK.r.test(l.href)) return;
        acts.append(link(l.href, l.txt, l.main ? 'go' : 'btn btn--ghost', 'sponsored noopener noreferrer', ' (abre em nova aba)'));
        if (l.w) { const w = d.createElement('span'); w.className = 'alt-when'; w.textContent = l.w; acts.append(w); }
      });
      if (o.alerta && OK.tg.test(o.alerta)) acts.append(link(o.alerta, 'Me avise se baixar (Telegram)', 'btn btn--ghost', 'noopener noreferrer', ' (abre o Telegram)'));
      if (OK.pag.test(o.pag)) acts.append(link(o.pag, 'Página do livro', 'link'));
      txt('.m-n', list.length > 1 ? (idx + 1) + '/' + list.length : '');
      $('.js-mprev', dlg).hidden = $('.js-mnext', dlg).hidden = list.length < 2;
    };
    const open = (id, push) => {
      const o = byId.get(id);
      if (!o || !OK.pag.test(o.pag)) return false;
      idx = Math.max(0, list.indexOf(id));
      fill(o);
      if (!dlg.open) dlg.showModal();
      if (push) history.pushState({ modal: id }, '', o.pag);
      else history.replaceState({ modal: id }, '', o.pag);
      return true;
    };
    const visiveis = () => [...new Set($$('a[data-modal]').filter(a => a.offsetParent).map(a => a.dataset.modal))];
    d.addEventListener('click', e => {
      const a = e.target.closest('a[data-modal]');
      if (!a || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button) return;
      list = visiveis(); opener = a;
      if (open(a.dataset.modal, !dlg.open)) e.preventDefault();
    });
    const passo = k => { if (list.length) { idx = (idx + k + list.length) % list.length; open(list[idx], false); } };
    $('.js-mprev', dlg).addEventListener('click', () => passo(-1));
    $('.js-mnext', dlg).addEventListener('click', () => passo(1));
    $('.js-mx', dlg).addEventListener('click', () => dlg.close());
    dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener('close', () => {
      if (!porPop && history.state && history.state.modal) history.back();
      porPop = false;
      if (opener) opener.focus();
    });
    addEventListener('popstate', e => {
      const id = e.state && e.state.modal;
      if (id && byId.has(id)) { fill(byId.get(id)); if (!dlg.open) dlg.showModal(); }
      else if (dlg.open) { porPop = true; dlg.close(); }
    });
  }
})();
