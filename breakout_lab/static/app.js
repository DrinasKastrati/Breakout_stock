"use strict";
const $ = (selector) => document.querySelector(selector);
const S = window.Strategies;
const state = { data: null, selected: null, chart: null, strategy: S.initial(), rows: {} };
const price = (v) => Number.isFinite(v) ? v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";
const number = (v, digits = 2) => Number.isFinite(v) ? v.toLocaleString("sv-SE", { maximumFractionDigits: digits }) : "—";
const LEVEL_STYLE = { resistance: ["#ecc58a", [4, 4]], r1: ["#ecc58a", []], r2: ["#b392f0", [5, 4]], t1: ["#b392f0", [5, 4]],
  t2: ["#b392f0", [2, 4]], s1: ["#7d8da1", []], s2: ["#7d8da1", [2, 4]], stop: ["#f58a9e", []] };
const exitLabels = { stop: "Stop", stop_gap: "Gap under stop", target: "Mål", time: "Tidsgräns" };
const BACKTEST_COPY = {
  breakout: ["Ger MACD ett bättre urval?", "Jämför samma breakoutstrategi med och utan volym och MACD.", "FORSKNING", "Separata affärer per aktie. Resultatet är ingen simulerad portföljavkastning."],
  metro: ["Tillför marknadsläget något?", "Jämför Metro med och utan marknadsläge (Risk-off nedgraderar köp).", "VISNING, INTE BEVIS", "Det rullande året ses löpande och kan inte avgöra om Metro fungerar. Bedömningen kräver ett protokoll med kriterier som sätts före körningen."]
};
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function link(text, href, className = "ext-link") {
  const a = el("a", text, className);
  // External text is data: only plain https links, opened without opener access.
  if (/^https:\/\//.test(href || "")) { a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; }
  return a;
}
function error(message) { $("#error").textContent = message; $("#error").classList.toggle("hidden", !message); }
async function api(path, options) {
  if (window.BreakoutData?.static) return window.BreakoutData.request(path, options);
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Det gick inte att läsa data.");
  return data;
}
const def = () => S.get(state.strategy);
const others = () => S.active().filter(s => s.id !== state.strategy);
function rowsFor(id) { return !state.data ? [] : id === "breakout" ? state.data.rows : (state.data.strategies?.[id]?.rows || []); }
function countsFor(id) { return id === "breakout" ? state.data.counts : (state.data.strategies?.[id]?.counts || {}); }
function rowFor(id, symbol) { return state.rows[id]?.get(symbol); }
function badge(row, id = state.strategy, className = "") {
  return el("span", S.get(id).labels[row.status] || row.status, `status ${row.status} ${className}`.trim());
}
function cell(type, value) {
  if (type === "price") return price(value);
  if (type === "times") return value === undefined || value === null ? "—" : `${number(value)}×`;
  if (type === "score") return `${value || 0}`;
  if (type === "trend") return S.trendLabels[value] || "—";
  return number(value);
}
function fillSettings(config) {
  for (const input of $("#settings-form").querySelectorAll("input")) {
    const metro = input.name.startsWith("metro.");
    const key = metro ? input.name.slice(6) : input.name;
    const v = metro ? config.metro?.[key] : config[key];
    if (input.type === "checkbox") input.checked = Boolean(v);
    else if (["min_dollar_volume", "min_market_cap"].includes(key)) input.value = v / 1e6;
    else if (["risk_fraction", "max_position_fraction", "breadth_risk_on", "breadth_risk_off"].includes(key)) input.value = v * 100;
    else if (Array.isArray(v)) input.value = v.join(", ");
    else input.value = v;
  }
}
function renderSwitch() {
  const box = $("#strategy-switch"); box.replaceChildren();
  for (const s of S.list) {
    const button = el("button", s.name, "switch-button"); button.type = "button";
    if (s.disabled) { button.disabled = true; button.title = "Kommer"; }
    else { button.setAttribute("aria-pressed", String(s.id === state.strategy)); button.addEventListener("click", () => setStrategy(s.id)); }
    box.append(button);
  }
}
function applyStrategy() {
  const d = def(), n = S.active().indexOf(d) + 1;
  document.body.dataset.strategy = d.id;
  renderSwitch();
  $("#screener-eyebrow").textContent = d.eyebrow; $("#screener-title").textContent = d.title; $("#screener-lead").textContent = d.lead;
  $("#strategy-number").textContent = `STRATEGI ${String(n).padStart(2, "0")} · ${d.name.toUpperCase()}`;
  const note = $("#strategy-note"); note.replaceChildren();
  d.note.forEach((line, i) => { if (i) note.append(el("br")); note.append(line); });
  $("#table-foot").textContent = d.tableFoot;
  $("#candidates-label").textContent = d.id === "breakout" ? "REGELPOÄNG / 100" : "R/R TILL T1";
  $("#plan-title").textContent = d.id === "breakout" ? "Plan för vald kandidat" : "Metro-analys i fem steg";
  $("#export-csv").href = `/api/export?strategy=${d.id}`;
  for (const node of document.querySelectorAll("[data-strategy-section]")) node.classList.toggle("hidden", node.dataset.strategySection !== d.id);
  for (const node of document.querySelectorAll(".breakout-only")) node.classList.toggle("hidden", d.id !== "breakout");
  for (const node of document.querySelectorAll(".metro-only")) node.classList.toggle("hidden", d.id !== "metro");
  const [title, lead, label, notice] = BACKTEST_COPY[d.id];
  $("#backtest-title").textContent = title; $("#backtest-lead").textContent = lead;
  $("#backtest-notice-label").textContent = label; $("#backtest-notice").textContent = notice;
  resetBacktest();
  const legend = $("#chart-legend"); legend.replaceChildren();
  const keys = d.id === "breakout" ? [["line-key", "SMA 50"], ["dash-key", "Motstånd"]]
    : [["line-key", "SMA 50"], ["key r1", "R1"], ["key target", "Mål"], ["key support", "Stöd"], ["key stop", "Stop"]];
  for (const [cls, text] of keys) legend.append(el("i", undefined, cls), ` ${text} `);
}
function fillFilter() {
  const select = $("#status-filter"); select.replaceChildren();
  for (const [value, text] of def().filters) { const option = el("option", text); option.value = value; select.append(option); }
}
function stat(label, value, hint, className) {
  const box = el("div", undefined, "stat");
  box.append(el("span", label), el("strong", String(value), className || undefined), el("small", hint));
  return box;
}
function renderStats() {
  const d = def(), counts = countsFor(d.id), meta = state.data.metadata;
  const box = $("#stats");
  box.replaceChildren(stat("Aktier i dataset", rowsFor(d.id).length, `Senaste session: ${meta.as_of || "—"}`));
  for (const [key, label, hint, cls] of d.stats) box.append(stat(label, counts[key] ?? 0, hint, cls));
  const regime = d.id === "metro" ? state.data.strategies?.metro?.regime : null;
  $("#regime-notice").classList.toggle("hidden", !regime);
  if (regime) {
    const index = regime.index_sma200 === null || regime.index_sma200 === undefined ? "index saknar SMA 200"
      : `index ${regime.index_close > regime.index_sma200 ? "över" : "under"} SMA 200`;
    const breadth = regime.breadth === null || regime.breadth === undefined ? "bredd —" : `${number(regime.breadth * 100, 0)} % över SMA 50`;
    $("#regime-text").textContent = [`${S.regimeLabels[regime.label]} · ${index} · ${breadth} (${regime.eligible} behöriga)`, ...(regime.notes || [])].join(" · ");
    $("#regime-notice").dataset.regime = regime.label;
  }
}
async function refresh() {
  const button = $("#refresh"); button.disabled = true; error("");
  try {
    state.data = await api("/api/scan");
    state.rows = Object.fromEntries(S.active().map(s => [s.id, new Map(rowsFor(s.id).map(r => [r.symbol, r]))]));
    const { metadata, config } = state.data;
    $("#source-badge").textContent = `${metadata.synthetic ? "DEMO" : metadata.source.toUpperCase()} · ${metadata.feed.toUpperCase()} · 1D`;
    $("#demo-notice").classList.toggle("hidden", !metadata.synthetic);
    fillSettings(config);
    if (window.BreakoutData?.static) $("#settings-status").textContent = "STYRS VIA GITHUB";
    renderDataDetails(metadata);
    renderStats();
    renderRows();
    state.chart = null;
    await selectDefault();
  } catch (e) { error(e.message); }
  finally { button.disabled = false; }
}
async function selectDefault() {
  const rows = rowsFor(state.strategy), d = def();
  const selected = rows.find(r => r.symbol === state.selected) || rows.find(r => d.candidates.includes(r.status)) || rows[0];
  if (selected) await select(selected.symbol);
}
function renderRows() {
  if (!state.data) return;
  const d = def(), query = $("#search").value.toLowerCase().trim(), filter = $("#status-filter").value;
  const head = $("#candidates-head"); head.replaceChildren();
  for (const text of ["Aktie", "Status", ...d.columns.map(c => c[0]), ...others().map(o => o.name)]) head.append(el("th", text));
  const rows = rowsFor(d.id).filter(r => (`${r.symbol} ${r.name}`).toLowerCase().includes(query) &&
    (filter === "all" || (filter === "candidates" ? d.candidates.includes(r.status) : r.status === filter)));
  const body = $("#candidates-body"); body.replaceChildren();
  if (!rows.length) {
    const empty = el("td", "Inga aktier matchar filtret. Välj ”Alla aktier” för att se varför kandidater sorterats bort.", "empty");
    empty.colSpan = 2 + d.columns.length + others().length; const tr = el("tr"); tr.append(empty); body.append(tr); return;
  }
  for (const row of rows) {
    const tr = el("tr", undefined, row.symbol === state.selected ? "selected" : "");
    const symbolCell = el("td"), button = el("button", undefined, "symbol-button");
    button.append(el("strong", row.symbol), el("small", row.name));
    button.addEventListener("click", () => select(row.symbol).catch(e => error(e.message)));
    symbolCell.append(button); tr.append(symbolCell);
    const statusCell = el("td"); statusCell.append(badge(row)); tr.append(statusCell);
    for (const [, key, type] of d.columns) tr.append(el("td", cell(type, row[key]), type === "score" ? "score" : undefined));
    for (const other of others()) {
      const td = el("td"), o = rowFor(other.id, row.symbol);
      if (o) td.append(badge(o, other.id, "mini")); else td.textContent = "—";
      tr.append(td);
    }
    body.append(tr);
  }
}
function renderChips(symbol) {
  const box = $("#strategy-chips"); box.replaceChildren();
  for (const other of others()) {
    const o = rowFor(other.id, symbol);
    const chip = el("button", `${other.name}: ${o ? other.labels[o.status] || o.status : "—"}`, "chip");
    chip.type = "button"; chip.title = `Visa ${other.name} för ${symbol}`;
    chip.addEventListener("click", () => setStrategy(other.id));
    box.append(chip);
  }
}
function planItem(label, value) { const item = el("div", undefined, "plan-item"); item.append(el("span", label), el("strong", value)); return item; }
function renderBreakoutPlan(row) {
  const plan = $("#trade-plan"); plan.replaceChildren();
  for (const [label, value] of [["Entryreferens", row.entry_reference], ["Stop", row.stop], ["Mål", row.target], ["Antal aktier", row.shares], ["Planerad risk, USD", row.risk_usd], ["Relativ styrka, 63d", row.relative_strength]]) {
    plan.append(planItem(label, label === "Relativ styrka, 63d" ? (value === null || value === undefined ? "—" : `${number(value*100)} pp`) : label === "Antal aktier" ? number(value, 0) : price(value)));
  }
  const reasons = $("#candidate-reasons"); reasons.replaceChildren();
  for (const reason of row.reasons || []) reasons.append(el("p", reason));
  for (const warning of row.warnings || []) reasons.append(el("p", `△ ${warning}`, "warning"));
}
function reactionText(reaction) {
  if (!reaction) return "Reaktion okänd än";
  if (reaction.label === "none") return "Ingen tydlig reaktion";
  const excess = `${reaction.excess >= 0 ? "+" : ""}${number(reaction.excess * 100, 1)} % mot index`;
  return `${reaction.label === "positive" ? "Positivt" : "Negativt"} mottagen ${excess}, ${number(reaction.rvol, 1)}× volym`;
}
function step(title, ...children) {
  const box = el("div", undefined, "metro-step"); box.append(el("h3", title), ...children); return box;
}
function grid(items) { const box = el("div", undefined, "trade-plan"); box.append(...items.map(([l, v]) => planItem(l, v))); return box; }
function veckoLinks(symbol) {
  const box = el("div", undefined, "metro-actions");
  const issue = `https://github.com/DrinasKastrati/Vecko_agent/issues/new?title=${encodeURIComponent("analys: " + symbol)}&body=${encodeURIComponent("Begäran om aktieanalys för " + symbol + ". Skicka in ärendet så köas det automatiskt.")}`;
  box.append(link("Djupanalys i Vecko_agent", issue, "button secondary"), link("Visa analyser", "https://drinaskastrati.github.io/Vecko_agent/"));
  return box;
}
function macroStep(row) {
  const section = state.data.strategies?.metro || {}, regime = section.regime, ctx = section.context;
  const parts = [el("p", `Marknadsläge: ${regime ? S.regimeLabels[regime.label] : "—"}${regime?.notes?.length ? " · " + regime.notes.join(" · ") : ""}`)];
  if (ctx?.narrative) {
    const head = el("p", `Marknadsberättelse från Vecko_agent scout-rapport, ${ctx.narrative.date}. `, "muted");
    head.append(link("Läs rapporten", ctx.narrative.url));
    parts.push(head, el("pre", ctx.narrative.text, "narrative"));
  } else parts.push(el("p", "Ingen färsk marknadsberättelse från Vecko_agent.", "muted"));
  if (!ctx) parts.push(el("p", "Nyhetskontext saknas i denna analys.", "muted"));
  else if (!ctx.shortlist.includes(row.symbol)) parts.push(el("p", "Inte i kortlistan: nyheter hämtas bara för Köp och utlösta Bevaka.", "muted"));
  else if (!ctx.news.available) parts.push(el("p", ctx.news.note || "Nyheter ej tillgängliga", "muted"));
  else {
    const news = ctx.news.by_symbol[row.symbol] || { articles: [], summary: { label: "none" } };
    const summary = news.summary.label === "none" ? "Ingen tydlig reaktion" : `${reactionText(news.summary)} (${news.summary.day})`;
    parts.push(el("p", `Marknadsreaktion, styr inte signalen: ${summary}`, "reaction-label"));
    if (!news.articles.length) parts.push(el("p", "Inga nyheter de senaste dagarna.", "muted"));
    const list = el("ul", undefined, "news-list");
    for (const article of news.articles) {
      const item = el("li"); item.append(link(article.headline || "(utan rubrik)", article.url));
      item.append(el("small", `${article.source || "okänd källa"} · ${(article.created_at || "").slice(0, 10)} · ${reactionText(article.reaction)}`));
      list.append(item);
    }
    if (news.articles.length) parts.push(list);
  }
  parts.push(veckoLinks(row.symbol));
  return step("1. Makro & sentiment", ...parts);
}
function renderMetroPlan(row) {
  const box = $("#metro-plan");
  if (row.status === "excluded" && row.r1 === null) {
    box.replaceChildren(step("Filtrerad", ...(row.reasons || []).map(r => el("p", r))), veckoLinks(row.symbol)); return;
  }
  const conclusion = [el("p", undefined)];
  conclusion[0].append(el("strong", S.get("metro").labels[row.status] || row.status));
  for (const reason of row.reasons || []) conclusion.push(el("p", reason));
  for (const warning of row.warnings || []) conclusion.push(el("p", `△ ${warning}`, "warning"));
  conclusion.push(el("p", "Håll positionsstorleken i proportion till portföljens totala risk. Status är ingen order.", "muted"));
  box.replaceChildren(
    macroStep(row),
    step("2. Nivåer", grid([["S2", price(row.s2)], ["S1", price(row.s1)], ["R1", price(row.r1)], ["R2", price(row.r2)], ["Trend", S.trendLabels[row.trend] || "—"], ["ATR", price(row.atr)]])),
    step("3. Scenarier",
      el("p", `Bullish: stängning över ${price(row.trigger)} → T1 ${price(row.t1)}, T2 ${price(row.t2)}.`),
      el("p", `Bearish: stängning under ${price(row.bear_trigger)} → ${price(row.bear_t1)}. Sälj om du äger, undvik annars.`),
      el("p", "Sidledes: mellan S1 och R1 — avvakta bekräftelse.")),
    step("4. Risk/Reward", grid([["Entryreferens", price(row.entry_reference)], ["Stop", price(row.stop)], ["T1", price(row.t1)], ["R/R", number(row.rr)], ["Antal aktier", number(row.shares, 0)], ["Planerad risk, USD", price(row.risk_usd)]])),
    step("5. Slutsats", ...conclusion));
}
async function select(symbol) {
  state.selected = symbol; renderRows();
  const dataset = state.data, d = def();
  const row = rowFor(d.id, symbol) || { symbol, name: "", status: "excluded", reasons: ["Aktien saknas i vald strategi"], checks: {} };
  $("#chart-symbol").textContent = symbol;
  $("#chart-name").textContent = row.name;
  $("#chart-price").textContent = row.close ? `$${price(row.close)}` : "—";
  $("#chart-status").replaceChildren(badge(row));
  renderChips(symbol);
  $("#signal-checks").replaceChildren(...Object.entries(row.checks || {}).map(([key, passed]) => el("span", `${passed ? "✓" : "·"} ${d.checks[key] || key}`, `check ${passed ? "passed" : ""}`)));
  const metro = d.id === "metro";
  $("#trade-plan").classList.toggle("hidden", metro); $("#candidate-reasons").classList.toggle("hidden", metro);
  $("#metro-plan").classList.toggle("hidden", !metro);
  if (metro) renderMetroPlan(row); else renderBreakoutPlan(row);
  if (state.chart?.symbol !== symbol) {
    state.chart = null; drawChart();
    const chart = await api(`/api/bars?symbol=${encodeURIComponent(symbol)}`);
    if (state.selected !== symbol || state.data !== dataset) return;
    state.chart = { ...chart, symbol };
  }
  drawChart();
  $("#chart-readout").textContent = "Pris / volym / MACD · för pekaren över diagrammet för OHLC.";
}
function setStrategy(id) {
  if (!S.get(id) || id === state.strategy) return;
  state.strategy = id; S.remember(id);
  applyStrategy(); fillFilter();
  if (!state.data) return;
  renderStats(); renderRows();
  (state.selected ? select(state.selected) : selectDefault()).catch(e => error(e.message));
}
function drawChart(hoverIndex) {
  const canvas = $("#chart"), ctx = canvas.getContext("2d");
  const width = canvas.clientWidth, height = canvas.clientHeight;
  if (!width || !height) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width*dpr); canvas.height = Math.round(height*dpr);
  ctx.scale(dpr, dpr); ctx.clearRect(0, 0, width, height);
  ctx.font = "10px system-ui";
  if (!state.chart) { ctx.fillStyle = "#98a7ba"; ctx.fillText("Läser diagram…", 22, 40); return; }
  const bars = state.chart.bars, ind = state.chart.indicators;
  if (!bars.length) return;
  const left = 18, right = width-59, top = 20, bottom = height*.55;
  const volumeTop = height*.60, volumeBottom = height*.73;
  const macdTop = height*.80, macdBottom = height-26;
  const dx = (right-left)/bars.length;
  const x = (i) => left+(i+.5)*dx;
  const maxPrice = Math.max(...bars.map(b => b.high))*1.01;
  const minPrice = Math.min(...bars.map(b => b.low))*.99;
  const y = (v) => bottom-(v-minPrice)/(maxPrice-minPrice)*(bottom-top);
  ctx.strokeStyle = "#25303f"; ctx.lineWidth = 1;
  for (let i=0; i<5; i++) {
    const value = minPrice+(maxPrice-minPrice)*i/4;
    ctx.beginPath(); ctx.moveTo(left,y(value)); ctx.lineTo(right,y(value)); ctx.stroke();
    ctx.fillStyle = "#98a7ba"; ctx.fillText(price(value),right+8,y(value)+3);
  }
  for (let i=0; i<bars.length; i++) {
    const b = bars[i]; ctx.strokeStyle = ctx.fillStyle = b.close >= b.open ? "#65e0b3" : "#f58a9e";
    ctx.beginPath(); ctx.moveTo(x(i),y(b.high)); ctx.lineTo(x(i),y(b.low)); ctx.stroke();
    ctx.fillRect(x(i)-Math.max(1,dx*.29),Math.min(y(b.open),y(b.close)),Math.max(2,dx*.58),Math.max(1,Math.abs(y(b.open)-y(b.close))));
  }
  function line(values, color, map) {
    ctx.strokeStyle = color; ctx.lineWidth = 1.3; ctx.beginPath(); let started = false;
    values.forEach((v,i) => { if (v === null || v === undefined) { started=false; return; } if (started) ctx.lineTo(x(i),map(v)); else ctx.moveTo(x(i),map(v)); started=true; }); ctx.stroke();
  }
  line(ind.sma50,"#8badff",y);
  // Only the active strategy's levels are drawn, so strategies never overlap in the chart.
  const row = rowFor(state.strategy, state.selected);
  const levels = state.strategy === "breakout" ? (row?.resistance ? [{ kind: "resistance", price: row.resistance, label: "" }] : []) : (row?.chart_levels || []);
  for (const level of levels) {
    if (!(level.price >= minPrice && level.price <= maxPrice)) continue;
    const [color, dash] = LEVEL_STYLE[level.kind] || ["#98a7ba", [2, 2]];
    ctx.strokeStyle = color; ctx.lineWidth = 1.2; ctx.setLineDash(dash); ctx.beginPath(); ctx.moveTo(left, y(level.price)); ctx.lineTo(right, y(level.price)); ctx.stroke(); ctx.setLineDash([]);
    if (level.label) { ctx.fillStyle = color; ctx.fillText(level.label, left + 4, y(level.price) - 4); }
  }
  const maxVolume = Math.max(...bars.map(b => b.volume),1);
  ctx.fillStyle="#98a7ba"; ctx.fillText("VOLYM",left,volumeTop-7);
  bars.forEach((b,i) => { ctx.fillStyle=b.close>=b.open?"#315d50":"#67434e";const h=(b.volume/maxVolume)*(volumeBottom-volumeTop);ctx.fillRect(x(i)-dx*.3,volumeBottom-h,Math.max(2,dx*.6),h); });
  const maxMACD = Math.max(...ind.macd.map(v=>Math.abs(v || 0)),...ind.signal.map(v=>Math.abs(v || 0)),.001)*1.15;
  const my = v => (macdTop+macdBottom)/2-v/maxMACD*(macdBottom-macdTop)/2;
  ctx.fillStyle="#98a7ba"; ctx.fillText("MACD 12, 26, 9",left,macdTop-8);
  ind.histogram.forEach((v,i)=>{if(v===null)return;ctx.fillStyle=v>=0?"#315d50":"#67434e";ctx.fillRect(x(i)-dx*.3,Math.min(my(v),my(0)),Math.max(1,dx*.6),Math.max(1,Math.abs(my(v)-my(0))));});
  line(ind.macd,"#8badff",my); line(ind.signal,"#ecc58a",my);
  ctx.fillStyle="#98a7ba";ctx.fillText(bars[0].date,left,height-8);ctx.textAlign="right";ctx.fillText(bars.at(-1).date,right,height-8);ctx.textAlign="left";
  if (hoverIndex !== undefined) {
    const i = Math.max(0,Math.min(bars.length-1,hoverIndex));
    ctx.strokeStyle="#93a6bf";ctx.setLineDash([2,4]);ctx.beginPath();ctx.moveTo(x(i),top);ctx.lineTo(x(i),macdBottom);ctx.stroke();ctx.setLineDash([]);
    const b=bars[i];$("#chart-readout").textContent=`${b.date} · O ${price(b.open)} · H ${price(b.high)} · L ${price(b.low)} · C ${price(b.close)} · Vol ${number(b.volume,0)}`;
  }
  canvas.setAttribute("aria-label", `${state.selected}, ${bars.length} dagliga candles från ${bars[0].date} till ${bars.at(-1).date}. Senaste stängning ${price(bars.at(-1).close)} USD.`);
}
function renderDataDetails(meta) {
  const target = $("#data-details"); target.replaceChildren();
  for (const text of [`Källa: ${meta.source}. Feed: ${meta.feed}. Senaste session: ${meta.as_of}.`, ...(meta.notes || [])]) target.append(el("p",text));
  if (meta.sample_limit) target.append(el("p",`Begränsat stickprov: ${meta.sample_limit} av ${meta.discovered_assets} upptäckta aktier.`));
}
function resetBacktest() {
  const body = $("#backtest-body"), empty = el("td", "Kör ett test för att jämföra varianterna.", "empty");
  empty.colSpan = 6; const tr = el("tr"); tr.append(empty); body.replaceChildren(tr);
  $("#backtest-detail").replaceChildren(); $("#trades-body").replaceChildren();
}
$("#export-csv").addEventListener("click", event => {
  if (!window.BreakoutData?.static) return;
  event.preventDefault();
  if (state.data) window.BreakoutData.exportCSV(rowsFor(state.strategy), def().csv, `${state.strategy}-scan.csv`);
});
$("#search").addEventListener("input",renderRows);
$("#status-filter").addEventListener("change",renderRows);
$("#refresh").addEventListener("click",refresh);
window.addEventListener("hashchange", () => setStrategy(window.location.hash.slice(1)));
$("#settings-form").addEventListener("submit",async event => {
  event.preventDefault(); const button = event.submitter; button.disabled=true; error("");
  try {
    const values={}, metro={...(state.data?.config?.metro || {})};
    for (const input of event.target.querySelectorAll("input")) {
      const isMetro = input.name.startsWith("metro."), key = isMetro ? input.name.slice(6) : input.name;
      let value;
      if(input.type==="checkbox") value=input.checked;
      else if (["allowed_sectors","excluded_symbols"].includes(key)) value=input.value.split(",").map(v=>v.trim()).filter(Boolean).map(v=>key==="excluded_symbols"?v.toUpperCase():v);
      else value=Number(input.value);
      if (isMetro) metro[key]=value; else values[key]=value;
    }
    for(const key of ["min_dollar_volume","min_market_cap"])values[key]*=1e6;
    for(const key of ["risk_fraction","max_position_fraction"])values[key]/=100;
    for(const key of ["breadth_risk_on","breadth_risk_off"])metro[key]/=100;
    values.metro=metro;
    await api("/api/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(values)});
    $("#settings-status").textContent="SPARAT"; await refresh();
  }catch(e){error(e.message);}finally{button.disabled=false;}
});
for (const button of document.querySelectorAll("[data-page]")) button.addEventListener("click",()=>{
  for(const page of document.querySelectorAll(".page")) page.classList.toggle("hidden",page.id!==`${button.dataset.page}-page`);
  for(const nav of document.querySelectorAll("[data-page]")){nav.classList.toggle("active",nav===button);if(nav===button)nav.setAttribute("aria-current","page");else nav.removeAttribute("aria-current");}
  $("#page-label").textContent=button.textContent.trim().replace(/^[^A-Za-zÅÄÖåäö]+/,"");error("");drawChart();
});
$("#chart").addEventListener("pointermove",event=>{
  if(!state.chart)return;const rect=event.currentTarget.getBoundingClientRect();const index=Math.floor((event.clientX-rect.left-18)/(rect.width-77)*state.chart.bars.length);drawChart(index);
});
$("#chart").addEventListener("pointerleave",()=>drawChart());
new ResizeObserver(()=>drawChart()).observe($("#chart"));
$("#backtest-form").addEventListener("submit",async event=>{
  event.preventDefault();const button=$("#backtest-run");button.disabled=true;button.textContent="Testar…";error("");
  try{
    const strategy=state.strategy;
    const params=new URLSearchParams({strategy});for(const key of ["start","end"]){const v=$(`#backtest-${key}`).value;if(v)params.set(key,v);}
    const result=await api(`/api/backtest?${params}`);
    if(strategy!==state.strategy)return;
    const body=$("#backtest-body");body.replaceChildren();
    for(const variant of result.variants){const s=variant.summary;const tr=el("tr");for(const text of [variant.name,s.trades,s.win_rate===null?"—":`${number(s.win_rate*100,1)} %`,number(s.expectancy_r),number(s.profit_factor_r),variant.open_trades])tr.append(el("td",text));body.append(tr);}
    const full=strategy==="breakout"?result.variants.at(-1):result.variants[0];
    $("#backtest-detail").replaceChildren(...full.limitations.map(t=>el("p",t)),el("p","Kostnader och exitregler följer config.json. Profit factor visas som — om testet saknar förluster."));
    const trades=$("#trades-body");trades.replaceChildren();
    for(const trade of full.trades.slice(-20).reverse()){const tr=el("tr");for(const text of [trade.symbol,trade.entry_date,trade.exit_date,`$${price(trade.pnl_usd)}`,number(trade.r_multiple),exitLabels[trade.exit_reason]])tr.append(el("td",text));trades.append(tr);}
    if(!full.trades.length){const tr=el("tr");const td=el("td","Inga avslutade affärer i vald period.","empty");td.colSpan=6;tr.append(td);trades.append(tr);}
  }catch(e){error(e.message);}finally{button.disabled=false;button.textContent=window.BreakoutData?.static?"Visa senaste jämförelse":"Kör jämförelse";}
});
applyStrategy(); fillFilter();
refresh();
if (window.BreakoutData?.static) setInterval(async () => {
  if (document.hidden || !state.data) return;
  try { if (await window.BreakoutData.hasUpdate()) await refresh(); }
  catch (_) { $("#site-status").textContent = "Ny analys kunde inte kontrolleras. Den visade sessionen gäller fortfarande; försök läsa senaste analys igen."; }
}, 5 * 60 * 1000);
