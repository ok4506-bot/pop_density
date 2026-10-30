/* 나이대별로 사는 곳과 들어오는 곳 — page script (Leaflet + Plotly, all vendored) */
(() => {
  'use strict';

  const REPO_URL = 'https://github.com/ok4506-bot/pop_density';  // 저장소 이름을 바꾸면 여기도 바꾸기

  // ---------------------------------------------------------------- helpers
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const css = getComputedStyle(document.documentElement);
  const V = k => css.getPropertyValue(k).trim();
  const fmt = n => (n == null || isNaN(n)) ? '–' : Math.round(n).toLocaleString('ko-KR');
  const sgn = n => (n == null || isNaN(n)) ? '–' : (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(Math.round(n)).toLocaleString('ko-KR');
  const sgn1 = n => (n == null || isNaN(n)) ? '–' : (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(n).toFixed(1);
  const f2 = n => (n == null || isNaN(n)) ? '–' : n.toFixed(2);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const SK = ['s1', 's2', 's3', 's4', 's5'];
  const INK = V('--ink'), INK2 = V('--ink-2'), INK3 = V('--ink-3'), RULE = V('--rule-2');
  const DIV = [V('--c3'), V('--c2'), V('--c1'), V('--mid'), V('--w1'), V('--w2'), V('--w3')];
  const LQ_BR = [0.67, 0.83, 0.95, 1.05, 1.2, 1.5];
  const LQ_LAB = ['0.67', '0.83', '0.95', '1.05', '1.2', '1.5'];
  const NM_BR = [-30, -15, -5, 5, 15, 30];
  const NM_LAB = ['−30', '−15', '−5', '+5', '+15', '+30'];
  const SMALL_FILL = '#dde1e6', MIXED_FILL = '#c5ccd5';
  const COMP_COLORS = ['#2f3b4c', '#5d6b80', '#93a0b3', '#c9d1dc'];
  const FONT = V('--font');

  function cls(v, br) { if (v == null || isNaN(v)) return null; let i = 0; while (i < br.length && v >= br[i]) i++; return i; }
  const divColor = (v, br) => { const i = cls(v, br); return i == null ? null : DIV[i]; };
  const rgba = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };

  const state = {
    stage: 's2', region: 'capital', viewA: 'lq', yearA: 2024, dir: 'in', viewB: 'flow', nFlows: 30, year: '2024', gu: null,
    fac: { A: { univ: true, job: true, edu: true, newtown: true }, B: { univ: true, job: true, edu: true, newtown: true } },
  };
  let D, STG, COLOR;

  // ---------------------------------------------------------------- load
  const FILES = ['summary', 'capital_grid', 'capital_ts', 'toronto', 'shapes', 'od', 'age', 'facilities'];
  Promise.all(FILES.map(f => fetch(`data/${f}.json`).then(r => { if (!r.ok) throw new Error(`${f}.json (${r.status})`); return r.json(); })))
    .then(arr => { D = Object.fromEntries(FILES.map((f, i) => [f, arr[i]])); init(); })
    .catch(showErr);

  function showErr(err) {
    console.error(err);
    const b = $('#loadErr');
    b.hidden = false;
    b.innerHTML = location.protocol === 'file:'
      ? '자료 파일을 읽지 못했습니다. <b>index.html</b>을 직접 열면 브라우저가 자료 읽기를 막습니다. <b>배포전_확인.bat</b>으로 미리보기를 여세요.'
      : `자료 파일을 읽지 못했습니다: ${esc(err.message)}`;
  }

  function guard(name, fn) { try { fn(); } catch (e) { console.error(`[${name}]`, e); } }

  function init() {
    STG = Object.fromEntries(D.summary.stages.map(s => [s.key, s]));
    COLOR = Object.fromEntries(D.summary.stages.map(s => [s.key, s.color]));
    guard('numbers', bindNumbers);
    guard('ribbon', buildRibbon);
    guard('tables', buildTables);
    guard('hero', heroChart);
    guard('mapA', mapA);
    guard('mapB', mapB);
    guard('band', bandChart);
    guard('heat', heatChart);
    guard('scatter', scatterChart);
    guard('katex', () => renderMathInElement(document.body, {
      delimiters: [{ left: '\\[', right: '\\]', display: true }, { left: '\\(', right: '\\)', display: false }], throwOnError: false,
    }));
    const a = $('#repoLink'); if (a) a.href = REPO_URL;
    setStage(state.stage);
  }

  // ---------------------------------------------------------------- numbers in text
  function bindNumbers() {
    const S = D.summary, P = S.age_peaks['2024'];
    const B = Object.fromEntries(S.seoul_balance.map(r => [r.stage, r]));
    const y = D.age.years['2024'];
    let first = null; for (let a = 15; a <= 40; a++) if (y.net[a] > 0) { first = a; break; }
    const sc = S.scatter, gi = sc.names.indexOf('관악구');
    const dong = k => S.top_dong_lqin[k].slice(0, 5).map(n => n.split(' ').slice(1).join(' ')).join('·');
    const vals = {
      pos_range: `${first}~${P.last_pos_age}세`, peak_age: P.peak_age, peak: fmt(P.peak), min_age: P.min_age, min: fmt(-P.min),
      s1_net: sgn(B.s1.net), s1_rest_share: S.seoul_in_origin.s1['비수도권'].toFixed(1),
      s2_net: sgn(B.s2.net), s2_rest: sgn(B.s2['net_비수도권']), s2_gg: sgn(B.s2['net_경기']),
      s3_net: sgn(B.s3.net), s3_gg_share: Math.round(100 * B.s3['net_경기'] / B.s3.net),
      grid_n: fmt(S.grid.n), grid_ok: fmt(S.grid.n_ok), tor_n: fmt(S.toronto.n), removed: fmt(S.grid.removed),
      b_s2_0: S.bands.capital.s2[0].toFixed(2), b_s3_far: Math.max(...S.bands.capital.s3.slice(5, 7)).toFixed(2),
      t_s2_0: S.bands.toronto.s2[0].toFixed(2), t_s3_0: S.bands.toronto.s3[0].toFixed(2),
      top_s1: dong('s1'), top_s2: dong('s2'), top_s3: dong('s3'),
      s3_dest: S.s3_out_top.slice(0, 5).map(d => d.name).join('·'),
      gwanak_s1: gi >= 0 ? Math.round(sc.nm_s1[gi]) : null,
      gwanak_s2: gi >= 0 ? sgn(sc.nm_s2[gi]) : null, gwanak_s3: gi >= 0 ? sgn(sc.nm_s3[gi]) : null,
    };
    const T = S.ts, b0 = T.bands[String(T.years[0])], b1 = T.bands[String(T.years[T.years.length - 1])], BL = S.bands.labels;
    const argmax = a => a.indexOf(Math.max(...a));
    Object.assign(vals, {
      ts_s2_a: b0.s2[0].toFixed(2), ts_s2_b: b1.s2[0].toFixed(2),
      ts_s3_a: `${BL[argmax(b0.s3)]}km`, ts_s3_b: `${BL[argmax(b1.s3)]}km`,
      ts_s5_a0: b0.s5[0].toFixed(2), ts_s5_afar: Math.max(b0.s5[6], b0.s5[7]).toFixed(2), ts_s5_b: `${BL[argmax(b1.s5)]}km`,
    });
    $$('[data-k]').forEach(el => { const v = vals[el.dataset.k]; if (v != null) el.textContent = v; });
  }

  // ---------------------------------------------------------------- ribbon
  function buildRibbon() {
    const r = $('#ribbon');
    r.innerHTML = D.summary.stages.map(s =>
      `<button type="button" role="radio" aria-checked="false" data-k="${s.key}" style="--c:${s.color}"><b>${s.label}</b><span class="rn">${esc(s.name)}</span></button>`).join('');
    $$('button', r).forEach(b => b.addEventListener('click', () => setStage(b.dataset.k)));
    r.addEventListener('keydown', e => {
      if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      const i = SK.indexOf(state.stage) + (e.key === 'ArrowRight' ? 1 : -1);
      if (i >= 0 && i < SK.length) { setStage(SK[i]); $(`button[data-k="${SK[i]}"]`, r).focus(); e.preventDefault(); }
    });
  }

  function setStage(k) {
    state.stage = k;
    $$('#ribbon button').forEach(b => {
      const on = b.dataset.k === k;
      b.setAttribute('aria-checked', on); b.tabIndex = on ? 0 : -1;
    });
    guard('hero-hl', heroHighlight);
    guard('A', () => A && A.restyle());
    guard('B', () => B && B.restyle());
    guard('band-hl', bandHighlight);
    guard('heat-hl', heatHighlight);
    guard('scatter-up', scatterUpdate);
  }

  // ---------------------------------------------------------------- tables
  function buildTables() {
    const S = D.summary;
    const why = {
      s1: '진학·입직 이동. 기숙사·군부대가 가장 크게 흔들어 거주 쪽은 시설 보정',
      s2: '토론토 선행연구(Moos 2016)와 같은 구간이라 두 도시를 바로 비교',
      s3: '첫 아이·첫 집 마련 시기. 서울을 떠나는 나이인지 확인',
      s4: '이동이 적은 정착층 (비교 기준선)',
      s5: '구도심·외곽 잔류, 은퇴 이동',
    };
    $('#stageTable tbody').innerHTML = S.stages.map(s => `<tr>
      <td><span class="chip-s"><span class="sw" style="--c:${s.color}"></span>${esc(s.name)}</span></td><td>${s.label}</td><td>${why[s.key]}</td>
      <td class="num">${(100 * S.ref_share_capital[s.key]).toFixed(1)}%</td><td class="num">${(100 * S.ref_share_toronto[s.key]).toFixed(1)}%</td></tr>`).join('');

    $('#facTable tbody').innerHTML = S.facility_stats.map(f => `<tr>
      <td>${esc(f.name)} <span class="muted">(${f.n_fac}곳)</span></td><td><span class="sw" style="--c:${COLOR[f.stage]}"></span>${STG[f.stage].label}</td>
      <td class="num">${f2(f.grid_lq_near)} / ${f2(f.grid_lq_far)}</td>
      <td class="num">${f.dong_lqin_near != null ? `${f2(f.dong_lqin_near)} / ${f2(f.dong_lqin_far)}` : '–'}</td></tr>`).join('');

    $('#balTable tbody').innerHTML = S.seoul_balance.map(r => `<tr>
      <td><span class="sw" style="--c:${COLOR[r.stage]}"></span>${r.label}</td><td class="num">${fmt(r.in)}</td><td class="num">${fmt(r.out)}</td>
      <td class="num">${sgn(r.net)}</td><td class="num">${sgn1(r.net_per1000)}</td><td class="num">${sgn(r['net_경기'])}</td>
      <td class="num">${sgn(r['net_인천'])}</td><td class="num">${sgn(r['net_비수도권'])}</td></tr>`).join('');
  }

  // ---------------------------------------------------------------- plotly base
  const PCONF = { displayModeBar: false, responsive: true };
  const baseLayout = extra => Object.assign({
    font: { family: FONT, size: 12, color: INK2 },
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    hoverlabel: { bgcolor: '#fff', bordercolor: V('--rule'), font: { family: FONT, color: INK, size: 12 } },
  }, extra);
  const STAGE_RANGES = { s1: [19.5, 24.5], s2: [24.5, 34.5], s3: [34.5, 44.5], s4: [44.5, 64.5], s5: [64.5, 90.5] };

  // ---------------------------------------------------------------- hero: age schedule
  let heroLayout;
  function heroChart() {
    const seg = $('#yearSeg');
    $$('button', seg).forEach(b => b.addEventListener('click', () => {
      state.year = b.dataset.v;
      $$('button', seg).forEach(x => x.setAttribute('aria-pressed', x === b));
      drawHero();
    }));
    drawHero();
    let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(drawHero, 250); });
  }
  function drawHero() {
    const y = D.age.years[state.year], P = D.age.peaks[state.year];
    const traces = [
      { type: 'bar', x: y.age, y: y.net_rest, name: '비수도권과', marker: { color: '#a7b2c1' }, hovertemplate: '비수도권과 %{y:+,}명<extra></extra>' },
      { type: 'bar', x: y.age, y: y.net_cap, name: '경기·인천과', marker: { color: '#3b4a5f' }, hovertemplate: '경기·인천과 %{y:+,}명<extra></extra>' },
      { type: 'scatter', mode: 'lines', x: y.age, y: y.net, name: '합계', line: { color: INK, width: 2 }, hovertemplate: '합계 %{y:+,}명<extra></extra>' },
    ];
    const shapes = [], annotations = [], narrow = $('#ageChart').clientWidth < 560;
    D.summary.stages.forEach(s => {
      const [a, b] = STAGE_RANGES[s.key];
      shapes.push({ type: 'rect', xref: 'x', yref: 'paper', x0: a, x1: b, y0: 1.015, y1: 1.06, fillcolor: s.color, line: { width: 0 } });
      if (!narrow || ['s2', 's4', 's5'].includes(s.key)) annotations.push({ xref: 'x', yref: 'paper', x: (a + b) / 2, y: 1.075, yanchor: 'bottom', showarrow: false, text: s.label, font: { size: narrow ? 10 : 11, color: INK2 } });
    });
    annotations.push(
      { x: P.peak_age, y: y.net[P.peak_age], text: `${P.peak_age}세 ${sgn(P.peak)}명`, showarrow: true, arrowhead: 0, arrowcolor: INK3, ax: 46, ay: -10, font: { size: 12, color: INK }, bgcolor: 'rgba(255,255,255,.85)' },
      { x: P.min_age, y: y.net[P.min_age], text: `${P.min_age}세 ${sgn(P.min)}명`, showarrow: true, arrowhead: 0, arrowcolor: INK3, ax: 40, ay: 26, font: { size: 12, color: INK }, bgcolor: 'rgba(255,255,255,.85)' },
    );
    heroLayout = baseLayout({
      barmode: 'relative', bargap: 0.15, barcornerradius: 2,
      margin: { l: narrow ? 48 : 58, r: 10, t: 48, b: 48 },
      xaxis: { title: { text: '만 나이', standoff: 6 }, dtick: narrow ? 10 : 5, range: [-0.5, 90.5], showgrid: false, zeroline: false, ticks: 'outside', ticklen: 3, tickcolor: V('--rule'), fixedrange: true },
      yaxis: { tickformat: ',', zeroline: true, zerolinecolor: INK, zerolinewidth: 1, gridcolor: RULE, fixedrange: true, title: { text: '순이동 (명)', standoff: 4 } },
      legend: { orientation: 'h', x: 0, y: -0.2, yanchor: 'top', font: { size: 12 } },
      hovermode: 'x unified', shapes, annotations,
    });
    Plotly.react('ageChart', traces, heroLayout, PCONF).then(heroHighlight);
  }
  function heroHighlight() {
    if (!heroLayout) return;
    const base = heroLayout.shapes.filter(s => !s.name);
    const [a, b] = STAGE_RANGES[state.stage];
    const hl = { name: 'hl', type: 'rect', xref: 'x', yref: 'paper', x0: a, x1: b, y0: 0, y1: 1, fillcolor: rgba(COLOR[state.stage], 0.09), line: { width: 0 }, layer: 'below' };
    heroLayout.shapes = [...base, hl];
    Plotly.relayout('ageChart', { shapes: heroLayout.shapes });
  }

  // ---------------------------------------------------------------- leaflet base
  // 배경지도: 키가 필요 없는 타일만 쓴다. Esri Light Gray(글자 없는 회색 바탕) → 실패하면 OSM(회색 처리) → 그래도 실패하면 타일 없이
  // 아래 addContext()의 시군구 경계·이름만으로도 지도가 읽히게 한다. (CARTO는 2025년부터 API 키 없이는 'API KEY REQUIRED' 그림을 돌려줌)
  const TILE_SOURCES = [
    { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', opt: { maxZoom: 16, attribution: 'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors' } },
    { url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', opt: { maxZoom: 19, className: 'tiles-muted', attribution: '© OpenStreetMap contributors' } },
  ];
  function makeMap(id) {
    const map = L.map(id, { preferCanvas: true, minZoom: 6, maxZoom: 15, zoomSnap: 0.5, zoomDelta: 0.5, scrollWheelZoom: false, attributionControl: true });
    map.attributionControl.setPrefix(false);
    let src = 0, errs = 0, layer = null;
    const useTiles = i => {
      if (layer) map.removeLayer(layer);
      if (i >= TILE_SOURCES.length) { map.getContainer().classList.add('no-tiles'); return; }
      errs = 0;
      layer = L.tileLayer(TILE_SOURCES[i].url, TILE_SOURCES[i].opt);
      layer.on('tileerror', () => { if (++errs === 6) useTiles(++src); });
      layer.addTo(map);
    };
    useTiles(0);
    // 스크롤로 페이지를 내리다 지도가 확대되지 않도록: 지도를 한 번 누르면 휠 확대가 켜진다
    map.on('click focus', () => map.scrollWheelZoom.enable());
    map.on('mouseout blur', () => map.scrollWheelZoom.disable());
    const el = map.getContainer();
    if ('ResizeObserver' in window) new ResizeObserver(() => map.invalidateSize({ pan: false })).observe(el);
    const zcls = () => { const z = map.getZoom(); el.classList.toggle('z-mid', z >= 9.25); el.classList.toggle('z-hi', z >= 10.5); el.classList.toggle('show-flab', z >= 11.5); };
    map.on('zoomend', zcls); map.whenReady(zcls);
    const msg = L.DomUtil.create('div', 'map-msg', el); msg.textContent = '지도를 누르면 휠로 확대됩니다';
    map.once('click', () => msg.remove());
    return map;
  }

  // 시군구 경계선과 이름 (타일이 없어도 위치를 읽을 수 있게). 지도 데이터 위에 얹는다.
  function addContext(map, { lines = true } = {}) {
    if (!map.getPane('context')) { map.createPane('context'); map.getPane('context').style.zIndex = 450; map.getPane('context').style.pointerEvents = 'none'; }
    if (!map.getPane('names')) { map.createPane('names'); map.getPane('names').style.zIndex = 620; map.getPane('names').style.pointerEvents = 'none'; }
    const g = L.layerGroup();
    if (lines) {
      g.addLayer(L.geoJSON(D.shapes.sgg, { pane: 'context', interactive: false, style: f => ({ color: '#3d4757', weight: f.properties.seoul ? 0.5 : 0.7, opacity: 0.45, fill: false }) }));
    }
    // 낮은 확대: 시 이름 하나(서울·인천·고양시 등), 높은 확대: 구 이름
    const groups = {};
    Object.values(D.od.nodes).forEach(n => {
      const m = n.name.match(/^(.+시) (.+구)$/);
      const city = n.seoul ? '서울' : n.name.startsWith('인천 ') ? (/강화군|옹진군/.test(n.name) ? n.name.replace('인천 ', '') : '인천') : m ? m[1] : n.name;
      (groups[city] = groups[city] || []).push(n);
      if (n.seoul || n.name.startsWith('인천 ') || m) {
        const short = n.seoul ? n.name : m ? m[2] : n.name.replace('인천 ', '');
        g.addLayer(L.tooltip({ permanent: true, direction: 'center', interactive: false, className: 'slab slab-s', pane: 'names' })
          .setLatLng([n.lat, n.lon]).setContent(esc(short)));
      }
    });
    Object.entries(groups).forEach(([city, ns]) => {
      const lat = ns.reduce((a, n) => a + n.lat, 0) / ns.length, lon = ns.reduce((a, n) => a + n.lon, 0) / ns.length;
      const multi = ns.length > 1 || city === '서울';
      g.addLayer(L.tooltip({ permanent: true, direction: 'center', interactive: false, className: `slab ${multi ? 'slab-o slab-city' : 'slab-o slab-keep'}`, pane: 'names' })
        .setLatLng([lat, lon]).setContent(esc(city)));
    });
    return g;
  }

  const FAC_GLYPH = {
    univ: '<path d="M6 1 L11 10 L1 10 Z" fill="#182230" stroke="#fff" stroke-width="1.2"/>',
    job: '<rect x="1.5" y="1.5" width="9" height="9" fill="#182230" stroke="#fff" stroke-width="1.2"/>',
    edu: '<path d="M6 0.8 L11.2 6 L6 11.2 L0.8 6 Z" fill="#182230" stroke="#fff" stroke-width="1.2"/>',
    newtown: '<circle cx="6" cy="6" r="4.4" fill="#fff" stroke="#182230" stroke-width="2.2"/>',
  };
  const facSvg = (cat, title = '') => `<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="${title ? 'false' : 'true'}">${title ? `<title>${esc(title)}</title>` : ''}${FAC_GLYPH[cat]}</svg>`;

  function facilityLayer(map, key, regionOf) {
    const cats = D.facilities.cats;
    const groups = {};   // groups[region][cat]
    D.facilities.items.forEach(f => {
      const icon = L.divIcon({ className: 'fac-icon', html: facSvg(f.cat, `${f.name} (${cats[f.cat]})`), iconSize: [12, 12], iconAnchor: [6, 6] });
      const m = L.marker([f.lat, f.lon], { icon, keyboard: false, zIndexOffset: 500 });
      m.bindTooltip(esc(f.name), { permanent: true, direction: 'right', offset: [7, 0], className: 'flab' });
      ((groups[f.region] = groups[f.region] || {})[f.cat] = groups[f.region][f.cat] || L.layerGroup()).addLayer(m);
    });
    const box = $(`.fac-chips[data-map="${key}"]`);
    const apply = () => {
      const reg = regionOf();
      Object.entries(groups).forEach(([r, byCat]) => Object.entries(byCat).forEach(([c, g]) => {
        if (r === reg && state.fac[key][c]) g.addTo(map); else map.removeLayer(g);
      }));
      $$('.chip', box).forEach(b => { b.hidden = !(groups[reg] && groups[reg][b.dataset.c]); });
    };
    box.innerHTML = Object.entries(cats).map(([c, name]) =>
      `<button type="button" class="chip" data-c="${c}" aria-pressed="${state.fac[key][c]}">${facSvg(c)}${esc(name)}</button>`).join('');
    $$('.chip', box).forEach(b => b.addEventListener('click', () => {
      const c = b.dataset.c; state.fac[key][c] = !state.fac[key][c]; b.setAttribute('aria-pressed', state.fac[key][c]); apply();
    }));
    apply();
    return apply;
  }

  function rampLegend(title, labels, extra = '') {
    return `<span class="lg-title">${title}</span><span><span class="ramp">${DIV.map(c => `<i style="background:${c}"></i>`).join('')}</span>
      <span class="ramp-labels" style="padding:0 18px">${labels.map(l => `<span>${l}</span>`).join('')}</span></span>${extra}`;
  }

  function lqBars(get) {
    return `<div class="bars">${SK.map(k => {
      const v = get(k), w = v == null ? 0 : Math.min(64, 32 * v);
      return `<span>${STG[k].label}</span><i style="width:${w}px;background:${COLOR[k]}"></i><span class="v">${f2(v)}</span>`;
    }).join('')}</div>`;
  }

  // ---------------------------------------------------------------- map A: residence LQ
  let A = null;
  function mapA() {
    const map = makeMap('mapA');
    const G = D.capital_grid, TS = D.capital_ts, SC = TS.scale;
    const Y = () => TS.by_year[String(state.yearA)];
    const lqAt = (k, i) => { const v = Y()[k][i]; return v == null ? null : v / SC; };
    const canvas = L.canvas({ padding: 0.3, tolerance: 0 });
    const grid = L.featureGroup();
    const polys = new Array(G.n);
    const c = G.corners;
    for (let i = 0; i < G.n; i++) {
      const q = c[i];
      const p = L.polygon([[q[1], q[0]], [q[3], q[2]], [q[5], q[4]], [q[7], q[6]]], { renderer: canvas, stroke: false, fillOpacity: 0.86, smoothFactor: 0 });
      p._i = i; polys[i] = p; grid.addLayer(p);
    }
    const tip = L.tooltip({ className: 'tt', direction: 'top', offset: [0, -6], sticky: true });
    grid.on('mousemove', e => {
      const i = e.layer._i, pop = Y().pop[i];
      const fac = state.yearA === 2024 && G.fac[i] ? `<div class="tt-m">시설 보정: ${esc(G.fac_codes[G.fac[i]])}</div>` : '';
      tip.setLatLng(e.latlng).setContent(`<div class="tt-h">${esc(G.names[G.name[i]])}</div><div class="tt-m">${state.yearA}년 · 인구 ${fmt(pop)}명 · 시청 ${G.dist[i]}km</div>${pop >= 250 ? lqBars(k => lqAt(k, i)) : '<div class="tt-m">인구 250명 미만 — LQ 비움</div>'}${fac}`);
      if (!map.hasLayer(tip)) tip.addTo(map);
    });
    grid.on('mouseout', () => map.removeLayer(tip));

    const tor = L.geoJSON(D.toronto, {
      renderer: canvas, style: () => ({ color: '#fff', weight: 0.4, fillOpacity: 0.86 }),
      onEachFeature: (f, l) => l.bindTooltip(() => {
        const p = f.properties;
        return `<div class="tt-h">CT ${esc(p.ct)}${p.city ? ' · 토론토시' : ''}</div><div class="tt-m">인구 ${fmt(p.pop)}명 · King &amp; Bay ${p.dist}km</div>${p.pop >= 250 ? lqBars(k => p[k]) : ''}`;
      }, { className: 'tt', sticky: true }),
    });
    const capBounds = grid.getBounds().pad(-0.12), torBounds = tor.getBounds().pad(-0.05);
    const ctx = addContext(map);
    const facA = facilityLayer(map, 'A', () => state.region);

    function fillOf(lqv, dom, pop) {
      if (state.viewA === 'dom') return dom >= 0 ? COLOR[SK[dom]] : dom === -1 ? MIXED_FILL : (pop > 0 ? SMALL_FILL : null);
      return lqv == null ? (pop > 0 ? SMALL_FILL : null) : divColor(lqv, LQ_BR);
    }
    function restyle() {
      const k = state.stage;
      if (state.region === 'capital') {
        const yd = Y();
        for (let i = 0; i < G.n; i++) {
          const v = yd[k][i], f = fillOf(v == null ? null : v / SC, yd.dom[i], yd.pop[i]);
          polys[i].setStyle({ fillColor: f || 'transparent', fillOpacity: f === SMALL_FILL ? 0.5 : 0.86 });
        }
      } else {
        tor.setStyle(ft => { const p = ft.properties, f = fillOf(p[k], p.dom, p.pop); return { fillColor: f || 'transparent', fillOpacity: f === SMALL_FILL ? 0.5 : 0.86 }; });
      }
      legendA(); captionA();
    }
    function legendA() {
      const el = $('#legendA');
      if (state.viewA === 'dom') {
        el.innerHTML = `<span class="lg-title">우세 생애단계</span>${D.summary.stages.map(s => `<span class="cat"><i style="background:${s.color}"></i>${s.label}</span>`).join('')}
          <span class="cat"><i style="background:${MIXED_FILL}"></i>혼합 (최고 LQ &lt; 1.2)</span><span class="cat"><i style="background:${SMALL_FILL}"></i>인구 250명 미만</span>`;
      } else {
        el.innerHTML = rampLegend(`${STG[state.stage].label}세 거주 LQ`, LQ_LAB, `<span class="cat"><i style="background:${SMALL_FILL}"></i>인구 250명 미만</span>`);
      }
    }
    function captionA() {
      const S = D.summary;
      if (state.region === 'capital') {
        const n = state.viewA === 'dom' ? ` ${STG[state.stage].label}세 우세 ${fmt(S.ts.dom_count[String(state.yearA)][state.stage])}격자.` : '';
        $('#capA').textContent = `수도권 1km 격자, ${state.yearA}년. 20~34세는 시설 인구 보정 후. 기준 = 그해 수도권 전체.${n}`;
      } else {
        $('#capA').textContent = '토론토 CMA 인구조사구(CT), 2021. 기준 = CMA 전체. CT는 1km 격자보다 크다(평균 약 5천 명).';
      }
    }
    function setRegion(r) {
      state.region = r;
      if (r === 'capital') { map.removeLayer(tor); grid.addTo(map); ctx.addTo(map); map.fitBounds(capBounds); }
      else { map.removeLayer(grid); map.removeLayer(ctx); tor.addTo(map); map.fitBounds(torBounds); }
      $('#yearsA').hidden = r !== 'capital';
      facA(); restyle(); drawBand();
    }
    // 연도 선택과 재생 (2000 → 2024)
    const ys = $('#yearASeg'), play = $('#playA');
    ys.innerHTML = TS.years.map(y => `<button type="button" data-v="${y}" aria-pressed="${y === state.yearA}">${y}</button>`).join('');
    const setYear = y => {
      state.yearA = y;
      $$('button', ys).forEach(b => b.setAttribute('aria-pressed', +b.dataset.v === y));
      restyle(); drawBand();
    };
    let timer = null;
    const stop = () => { clearInterval(timer); timer = null; play.textContent = '▶ 재생'; play.setAttribute('aria-pressed', 'false'); };
    $$('button', ys).forEach(b => b.addEventListener('click', () => { stop(); setYear(+b.dataset.v); }));
    play.addEventListener('click', () => {
      if (timer) { stop(); return; }
      play.textContent = '❚❚ 멈춤'; play.setAttribute('aria-pressed', 'true');
      let i = 0; setYear(TS.years[0]);
      timer = setInterval(() => { i += 1; if (i >= TS.years.length) { stop(); return; } setYear(TS.years[i]); }, 1300);
    });
    $$('#regionSeg button').forEach(b => b.addEventListener('click', () => { $$('#regionSeg button').forEach(x => x.setAttribute('aria-pressed', x === b)); setRegion(b.dataset.v); }));
    $$('#viewASeg button').forEach(b => b.addEventListener('click', () => { $$('#viewASeg button').forEach(x => x.setAttribute('aria-pressed', x === b)); state.viewA = b.dataset.v; restyle(); }));
    grid.addTo(map); ctx.addTo(map); map.fitBounds(capBounds);
    A = { map, restyle };
  }

  // ---------------------------------------------------------------- map B: movement
  let B = null;

  function arc(a, b, bend = 0.2, n = 28) {
    const [y1, x1] = a, [y2, x2] = b, mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1;
    const cx = mx - dy * bend, cy = my + dx * bend, pts = [];
    for (let t = 0; t <= 1.0001; t += 1 / n) {
      const u = 1 - t;
      pts.push([u * u * y1 + 2 * u * t * cy + t * t * y2, u * u * x1 + 2 * u * t * cx + t * t * x2]);
    }
    return pts;
  }

  function mapB() {
    const map = makeMap('mapB');
    const canvas = L.canvas({ padding: 0.3 });
    const SG = D.shapes.sgg, DG = D.shapes.dong, nodes = D.od.nodes;
    const byCode = {};

    const sgg = L.geoJSON(SG, {
      renderer: canvas,
      style: () => ({ color: '#fff', weight: 0.8, fillOpacity: 0.85 }),
      onEachFeature: (f, l) => {
        byCode[f.properties.code] = l;
        l.bindTooltip(() => sggTip(f.properties), { className: 'tt', sticky: true });
        l.on('click', () => { state.gu = f.properties.code; side(); highlight(); });
      },
    });
    const seoulOutline = L.geoJSON({ type: 'FeatureCollection', features: SG.features.filter(f => f.properties.seoul) }, {
      renderer: canvas, interactive: false, style: () => ({ color: INK, weight: 0.7, opacity: 0.55, fill: false }),
    });
    const dong = L.geoJSON(DG, {
      renderer: canvas,
      style: () => ({ color: '#fff', weight: 0.5, fillOpacity: 0.86 }),
      onEachFeature: (f, l) => l.bindTooltip(() => {
        const p = f.properties, k = state.stage;
        return `<div class="tt-h">${esc(p.gu)} ${esc(p.name)}</div><div class="tt-m">2024 전입(동 경계를 넘은) ${fmt(p.in_all)}명</div>
          <div>${STG[k].label}세 유입 LQ <b>${f2(p['lqin_' + k])}</b> · ${p['in_' + k] == null ? '5명 미만' : fmt(p['in_' + k]) + '명'}</div>`;
      }, { className: 'tt', sticky: true }),
    });
    const flows = L.layerGroup();
    const ctx = addContext(map, { lines: false });
    facilityLayer(map, 'B', () => 'capital');

    function sggTip(p) {
      const k = state.stage;
      return `<div class="tt-h">${esc(p.name)}</div><div class="tt-m">${STG[k].label}세 · 2024</div>
        <div>순유입 강도 <b>${sgn1(p['nm_' + k])}</b>‰ · 유입 LQ <b>${f2(p['lqin_' + k])}</b> · 거주 LQ <b>${f2(p['lq_' + k])}</b></div>
        <div class="tt-m">전입 ${fmt(p['in_' + k])} · 전출 ${fmt(p['out_' + k])} · 인구 ${fmt(p['pop_' + k])}</div>`;
    }

    function drawFlows() {
      flows.clearLayers();
      if (state.viewB !== 'flow') return;
      const k = state.stage, list = (D.od.flows[state.dir][k] || []).slice(0, state.nFlows);
      if (!list.length) return;
      const max = list[0][2], col = COLOR[k];
      list.slice().reverse().forEach(([o, d, n]) => {
        const a = nodes[o], b = nodes[d]; if (!a || !b) return;
        const w = 1.2 + 6.5 * Math.sqrt(n / max);
        const pts = arc([a.lat, a.lon], [b.lat, b.lon], 0.18);
        flows.addLayer(L.polyline(pts, { renderer: canvas, color: '#fff', weight: w + 2.6, opacity: 0.9, lineCap: 'round', interactive: false }));
        const line = L.polyline(pts, { renderer: canvas, color: col, weight: w, opacity: 0.95, lineCap: 'round' });
        line.bindTooltip(`<div class="tt-h">${esc(a.name)} → ${esc(b.name)}</div><div>${STG[k].label}세 <b>${fmt(n)}</b>명 (2024)</div>`, { className: 'tt', sticky: true });
        flows.addLayer(line);
        flows.addLayer(L.circleMarker([b.lat, b.lon], { renderer: canvas, radius: 2.2 + w / 3, color: '#fff', weight: 1.2, fillColor: INK, fillOpacity: 1, interactive: false }));
      });
    }

    function highlight() {
      sgg.eachLayer(l => {
        const on = l.feature.properties.code === state.gu;
        l.setStyle(on ? { color: INK, weight: 2.4 } : { color: '#fff', weight: 0.8 });
        if (on) l.bringToFront();
      });
    }

    function side() {
      const k = state.stage, el = $('#side'), comp = D.od.comp[k], cats = comp.cats;
      const code = state.gu;
      const p = code ? byCode[code] && byCode[code].feature.properties : null;
      let head, kv, cin, cout, note = '';
      if (p) {
        head = `<h4>${esc(p.name)}</h4><div class="muted">${STG[k].label}세 · 2024 · <a href="#" id="clearGu">서울 전체 보기</a></div>`;
        kv = [['순유입 강도', `${sgn1(p['nm_' + k])}‰`], ['유입 LQ', f2(p['lqin_' + k])], ['거주 LQ', f2(p['lq_' + k])], ['전입 / 전출', `${fmt(p['in_' + k])} / ${fmt(p['out_' + k])}`]];
        cin = comp.in[code]; cout = comp.out[code];
        if (!p.seoul) note = '<p class="muted">출발지·도착지 구성은 서울 25개 구만 계산했습니다.</p>';
      } else {
        const r = D.summary.seoul_balance.find(x => x.stage === k);
        head = `<h4>서울 전체</h4><div class="muted">${STG[k].label}세 · 2024 · 지도에서 구를 누르면 바뀝니다</div>`;
        kv = [['서울 밖에서 전입', fmt(r.in)], ['서울 밖으로 전출', fmt(r.out)], ['순이동', sgn(r.net)], ['인구 천 명당', `${sgn1(r.net_per1000)}‰`]];
        const sum = obj => Object.values(obj).reduce((acc, v) => acc.map((x, i) => x + v[i]), [0, 0, 0, 0]);
        cin = sum(comp.in); cout = sum(comp.out);
        const rl = obj => Object.entries(obj || {}).sort((a, b) => b[1] - a[1]).map(([r, n]) => `${r} ${fmt(n)}`).join(' · ');
        note = `<p class="muted">비수도권 권역별 — 들어온 사람: ${rl(D.od.flows.region_in[k])}<br>나간 사람: ${rl(D.od.flows.region_out[k])}</p>`;
      }
      const bar = (title, arr, labs) => {
        if (!arr) return '';
        const tot = arr.reduce((a, b) => a + b, 0) || 1;
        return `<div class="comp"><div class="comp-title">${title} (${fmt(tot)}명)</div>
          <div class="comp-bar">${arr.map((v, i) => v > 0 ? `<span style="width:${100 * v / tot}%;background:${COMP_COLORS[i]}" title="${labs[i]} ${fmt(v)}명"></span>` : '').join('')}</div>
          <div class="comp-legend">${arr.map((v, i) => `<i style="background:${COMP_COLORS[i]}"></i><span>${labs[i]}</span><b>${(100 * v / tot).toFixed(0)}%</b>`).join('')}</div></div>`;
      };
      const labs = cats.map(c => c === '서울' ? (p ? '서울 다른 구' : '서울 안 다른 구') : c);
      el.innerHTML = `${head}<div class="kv">${kv.map(([a, b]) => `<span>${a}</span><span>${b}</span>`).join('')}</div>
        ${bar('들어온 사람의 출발지', cin, labs)}${bar('나간 사람의 도착지', cout, labs)}${note}`;
      const clr = $('#clearGu'); if (clr) clr.addEventListener('click', e => { e.preventDefault(); state.gu = null; side(); highlight(); });
    }

    function restyle() {
      const k = state.stage;
      if (state.viewB === 'flow') {
        sgg.setStyle(f => ({ fillColor: divColor(f.properties['nm_' + k], NM_BR) || SMALL_FILL }));
      } else {
        dong.setStyle(f => { const v = f.properties['lqin_' + k]; return { fillColor: v == null ? SMALL_FILL : divColor(v, LQ_BR) }; });
      }
      highlight(); drawFlows(); side(); legendB();
    }
    function legendB() {
      const k = state.stage;
      if (state.viewB === 'flow') {
        $('#legendB').innerHTML = rampLegend(`${STG[k].label}세 순유입 강도 (‰)`, NM_LAB,
          `<span class="cat"><i style="background:${COLOR[k]};height:4px;width:22px"></i>이동 경로 (두께 = 명, 점 = 도착지)</span>`);
        $('#capB').textContent = `색 = 시군구 순유입 강도(③). 선 = 경기·인천 시군구와 서울 구 사이 ${STG[k].label}세 이동 상위 ${state.nFlows}개(${state.dir === 'in' ? '서울로 들어오기' : '서울에서 나가기'}, 2024, ${D.od.flow_min}명 이상).`;
      } else {
        $('#legendB').innerHTML = rampLegend(`${STG[k].label}세 유입 LQ (서울 행정동)`, LQ_LAB, `<span class="cat"><i style="background:${SMALL_FILL}"></i>5명 미만·전입 100명 미만</span>`);
        $('#capB').textContent = '서울 행정동 유입 LQ(②), 2024. 같은 동 안 이사는 제외, 기준 = 수도권 행정동 전입 전체. 굵은 선 = 구 경계.';
      }
    }
    function setView(v) {
      state.viewB = v;
      if (v === 'flow') { map.removeLayer(dong); map.removeLayer(seoulOutline); sgg.addTo(map); flows.addTo(map); map.fitBounds(capBounds); }
      else { map.removeLayer(sgg); map.removeLayer(flows); dong.addTo(map); seoulOutline.addTo(map); map.fitBounds(seoulBounds); }
      $('#nFlows').disabled = v !== 'flow'; $$('#dirSeg button').forEach(b => { b.disabled = v !== 'flow'; });
      restyle();
    }
    $$('#dirSeg button').forEach(b => b.addEventListener('click', () => { $$('#dirSeg button').forEach(x => x.setAttribute('aria-pressed', x === b)); state.dir = b.dataset.v; drawFlows(); legendB(); }));
    $$('#viewBSeg button').forEach(b => b.addEventListener('click', () => { $$('#viewBSeg button').forEach(x => x.setAttribute('aria-pressed', x === b)); setView(b.dataset.v); }));
    const nf = $('#nFlows'), nfo = $('#nFlowsOut');
    nf.addEventListener('input', () => { state.nFlows = +nf.value; nfo.textContent = nf.value; drawFlows(); legendB(); });

    const capBounds = L.latLngBounds([36.95, 126.45], [38.05, 127.75]);
    const seoulBounds = seoulOutline.getBounds().pad(0.02);
    sgg.addTo(map); flows.addTo(map); ctx.addTo(map); map.fitBounds(capBounds);
    B = { map, restyle };
  }

  // ---------------------------------------------------------------- band curves (small multiples, one y axis)
  function bandChart() { drawBand(); }
  function drawBand() {
    const el = $('#bandChart'); if (!el) return;
    const S = D.summary.bands, labels = S.labels, traces = [];
    const capY = (D.summary.ts && D.summary.ts.bands[String(state.yearA)]) || S.capital;
    ['capital', 'toronto'].forEach((r, j) => {
      D.summary.stages.forEach(s => traces.push({
        type: 'scatter', mode: 'lines+markers', x: labels, y: r === 'capital' ? capY[s.key] : S[r][s.key], name: s.label, legendgroup: s.key, showlegend: j === 0,
        xaxis: j ? 'x2' : 'x', yaxis: 'y', line: { color: s.color, width: 1.6 }, marker: { size: 5, color: s.color },
        hovertemplate: `${r === 'capital' ? '수도권' : '토론토'} %{x}km · ${s.label}세 LQ %{y:.2f}<extra></extra>`, _k: s.key,
      }));
    });
    const ref = ['x', 'x2'].map(x => ({ type: 'line', xref: `${x} domain`, yref: 'y', x0: 0, x1: 1, y0: 1, y1: 1, line: { color: INK3, width: 1, dash: 'dot' } }));
    const layout = baseLayout({
      margin: { l: 44, r: 8, t: 30, b: 70 }, showlegend: true,
      legend: { orientation: 'h', x: 0, y: -0.3, yanchor: 'top', font: { size: 12 } },
      xaxis: { domain: [0, 0.48], tickangle: -40, tickfont: { size: 10 }, title: { text: '서울시청에서 (km)', font: { size: 11 } }, fixedrange: true, showgrid: false },
      xaxis2: { domain: [0.52, 1], tickangle: -40, tickfont: { size: 10 }, title: { text: 'King & Bay에서 (km)', font: { size: 11 } }, fixedrange: true, showgrid: false },
      yaxis: { range: [0.6, 2.0], gridcolor: RULE, zeroline: false, fixedrange: true, title: { text: '거주 LQ', standoff: 2 } },
      annotations: [
        { xref: 'x domain', yref: 'paper', x: 0, y: 1.06, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: `<b>수도권</b> ${state.yearA}`, font: { size: 12, color: INK } },
        { xref: 'x2 domain', yref: 'paper', x: 0, y: 1.06, xanchor: 'left', yanchor: 'bottom', showarrow: false, text: '<b>토론토</b> 2021', font: { size: 12, color: INK } },
      ],
      shapes: ref, hovermode: 'closest',
    });
    Plotly.react(el, traces, layout, PCONF).then(bandHighlight);
  }
  function bandHighlight() {
    const el = $('#bandChart'); if (!el || !el.data) return;
    const k = state.stage;
    const w = el.data.map(t => t._k === k ? 3.2 : 1.4), o = el.data.map(t => t._k === k ? 1 : 0.35), ms = el.data.map(t => t._k === k ? 7 : 4);
    Plotly.restyle(el, { 'line.width': w, opacity: o, 'marker.size': ms });
  }

  // ---------------------------------------------------------------- heatmap (25 gu × 5 stages)
  function heatChart() {
    const H = D.summary.heat, xs = D.summary.stages.map(s => s.label);
    const cap = 60;
    const scale = [[0, DIV[0]], [0.25, DIV[1]], [0.42, DIV[2]], [0.5, DIV[3]], [0.58, DIV[4]], [0.75, DIV[5]], [1, DIV[6]]];
    const z = H.z.map(r => r.map(v => Math.max(-cap, Math.min(cap, v))));
    const annotations = [];
    H.z.forEach((row, i) => row.forEach((v, j) => {
      if (Math.abs(v) >= 30) annotations.push({ x: xs[j], y: H.names[i], text: Math.round(v).toString().replace('-', '−'), showarrow: false, font: { size: 10, color: Math.abs(v) >= 45 ? '#fff' : INK } });
    }));
    const layout = baseLayout({
      margin: { l: 66, r: 8, t: 26, b: 52 },
      xaxis: { side: 'top', fixedrange: true, tickfont: { size: 12, color: INK } },
      yaxis: { autorange: 'reversed', fixedrange: true, tickfont: { size: 12 } },
      annotations,
    });
    Plotly.newPlot('heatChart', [{
      type: 'heatmap', x: xs, y: H.names, z, zmin: -cap, zmax: cap, colorscale: scale, xgap: 2, ygap: 2,
      customdata: H.z, hovertemplate: '%{y} · %{x}세<br>인구 천 명당 %{customdata:+.1f}명<extra></extra>',
      colorbar: { orientation: 'h', thickness: 8, len: 0.7, x: 0.5, xanchor: 'center', y: -0.04, yanchor: 'top', tickvals: [-60, -30, 0, 30, 60], ticktext: ['−60↓', '−30', '0', '+30', '+60↑'], tickfont: { size: 10 }, outlinewidth: 0 },
    }], layout, PCONF).then(heatHighlight);
  }
  function heatHighlight() {
    const el = $('#heatChart'); if (!el || !el.layout) return;
    const j = SK.indexOf(state.stage);
    Plotly.relayout(el, { shapes: [{ type: 'rect', xref: 'x', yref: 'paper', x0: j - 0.5, x1: j + 0.5, y0: 0, y1: 1, line: { color: INK, width: 2 }, fillcolor: 'rgba(0,0,0,0)' }] });
  }

  // ---------------------------------------------------------------- scatter (① × ②, color = sign of ③)
  function scatterChart() { scatterUpdate(); }
  function scatterUpdate() {
    const el = $('#scatterChart'); if (!el) return;
    const S = D.summary.scatter, k = state.stage, n = S.names.length;
    const pts = [];
    for (let i = 0; i < n; i++) {
      const x = S['lq_' + k][i], y = S['lqin_' + k][i], m = S['nm_' + k][i], p = S['pop_' + k][i];
      if (x == null || y == null) continue;
      pts.push({ i, x, y, m, p, name: S.names[i], seoul: S.seoul[i] });
    }
    const score = q => Math.abs(Math.log(q.x)) + Math.abs(Math.log(q.y));
    const lab = new Set(pts.slice().sort((a, b) => score(b) - score(a)).slice(0, 7).map(q => q.i));
    const maxp = Math.max(...pts.map(q => q.p));
    const mk = (sel, name, color) => {
      const q = pts.filter(sel);
      return {
        type: 'scatter', mode: 'markers+text', name, x: q.map(v => v.x), y: q.map(v => v.y),
        text: q.map(v => lab.has(v.i) ? v.name : ''), textposition: 'top center', textfont: { size: 11, color: INK },
        customdata: q.map(v => [v.name, v.m, v.p]),
        marker: { color, size: q.map(v => 7 + 22 * Math.sqrt(v.p / maxp)), opacity: 0.88, line: { color: q.map(v => v.seoul ? INK : '#fff'), width: q.map(v => v.seoul ? 1.2 : 1) } },
        hovertemplate: '<b>%{customdata[0]}</b><br>거주 LQ %{x:.2f} · 유입 LQ %{y:.2f}<br>순유입 강도 %{customdata[1]:+.1f}‰ · 인구 %{customdata[2]:,}<extra></extra>',
      };
    };
    const xs = pts.map(q => q.x), ys = pts.map(q => q.y);
    const lo = v => Math.log10(Math.min(...v) * 0.88), hi = v => Math.log10(Math.max(...v) * 1.22);
    const xr = [Math.min(lo(xs), Math.log10(0.8)), Math.max(hi(xs), Math.log10(1.25))];
    const yr = [Math.min(lo(ys), Math.log10(0.8)), Math.max(hi(ys), Math.log10(1.25))];
    const q = t => ({ xref: 'paper', yref: 'paper', showarrow: false, font: { size: 11, color: INK3 }, ...t });
    const layout = baseLayout({
      margin: { l: 52, r: 10, t: 14, b: 76 },
      xaxis: { type: 'log', range: xr, title: { text: `${STG[k].label}세 거주 LQ (①, 로그)` }, gridcolor: RULE, zeroline: false, tickvals: [0.5, 0.7, 0.8, 1, 1.25, 1.5, 2, 3], fixedrange: true },
      yaxis: { type: 'log', range: yr, title: { text: `유입 LQ (②, 로그)` }, gridcolor: RULE, zeroline: false, tickvals: [0.5, 0.7, 0.8, 1, 1.25, 1.5, 2, 3], fixedrange: true },
      shapes: [
        { type: 'line', xref: 'x', yref: 'paper', x0: 1, x1: 1, y0: 0, y1: 1, line: { color: INK3, width: 1, dash: 'dot' } },
        { type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: 1, y1: 1, line: { color: INK3, width: 1, dash: 'dot' } },
      ],
      annotations: [
        q({ x: 0.99, y: 0.99, xanchor: 'right', yanchor: 'top', text: '많이 살고 많이 들어온다' }),
        q({ x: 0.01, y: 0.99, xanchor: 'left', yanchor: 'top', text: '새로 몰린다' }),
        q({ x: 0.99, y: 0.01, xanchor: 'right', yanchor: 'bottom', text: '살지만 덜 들어온다' }),
      ],
      legend: { orientation: 'h', x: 0, y: -0.17, yanchor: 'top' },
      hovermode: 'closest',
    });
    Plotly.react(el, [mk(v => v.m >= 0, '순유입 (남는 곳)', V('--w2')), mk(v => v.m < 0, '순유출 (빠지는 곳)', V('--c2'))], layout, PCONF);
    const ur = pts.filter(v => v.x >= 1 && v.y >= 1), urOut = ur.filter(v => v.m < 0);
    $('#scatterNote').textContent = `${STG[k].label}세: 오른쪽 위 ${ur.length}곳 중 ${urOut.length}곳이 순유출이다. 테두리가 진한 점이 서울 25개 구.`;
  }
})();
