"use strict";
const $ = (selector) => document.querySelector(selector);
const state = { data: null, selected: null, chart: null };
const labels = { breakout: "Breakout", watch: "Bevakning", extended: "Översträckt", inactive: "Ingen setup", excluded: "Filtrerad" };
const checkLabels = { trend: "Trend", base: "Bas", breakout: "Pris", volume: "Volym", macd: "MACD", not_extended: "Avstånd" };
const price = (v) => Number.isFinite(v) ? v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";
const number = (v, digits = 2) => Number.isFinite(v) ? v.toLocaleString("sv-SE", { maximumFractionDigits: digits }) : "—";
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function error(message) { $("#error").textContent = message; $("#error").classList.toggle("hidden", !message); }
async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Det gick inte att läsa data.");
  return data;
}
function badge(row) { return el("span", labels[row.status] || row.status, `status ${row.status}`); }
function fillSettings(config) {
  for (const input of $("#settings-form").querySelectorAll("input")) {
    const v = config[input.name];
    if (input.type === "checkbox") input.checked = Boolean(v);
    else if (["min_dollar_volume", "min_market_cap"].includes(input.name)) input.value = v / 1e6;
    else if (["risk_fraction", "max_position_fraction"].includes(input.name)) input.value = v * 100;
    else if (Array.isArray(v)) input.value = v.join(", ");
    else input.value = v;
  }
}
async function refresh() {
  const button = $("#refresh"); button.disabled = true; error("");
  try {
    state.data = await api("/api/scan");
    const { rows, counts, metadata, config } = state.data;
    $("#count-all").textContent = rows.length;
    for (const key of ["breakout", "watch", "excluded"]) $(`#count-${key}`).textContent = counts[key];
    $("#as-of").textContent = `Senaste session: ${metadata.as_of || "—"}`;
    $("#source-badge").textContent = `${metadata.synthetic ? "DEMO" : metadata.source.toUpperCase()} · ${metadata.feed.toUpperCase()} · 1D`;
    $("#demo-notice").classList.toggle("hidden", !metadata.synthetic);
    fillSettings(config);
    renderDataDetails(metadata);
    renderRows();
    const selected = rows.find(r => r.symbol === state.selected) || rows.find(r => ["breakout", "watch"].includes(r.status)) || rows[0];
    if (selected) await select(selected.symbol);
  } catch (e) { error(e.message); }
  finally { button.disabled = false; }
}
function renderRows() {
  if (!state.data) return;
  const query = $("#search").value.toLowerCase().trim();
  const filter = $("#status-filter").value;
  const rows = state.data.rows.filter(r => (`${r.symbol} ${r.name}`).toLowerCase().includes(query) &&
    (filter === "all" || (filter === "candidates" ? ["breakout", "watch"].includes(r.status) : r.status === filter)));
  const body = $("#candidates-body"); body.replaceChildren();
  if (!rows.length) {
    const cell = el("td", "Inga aktier matchar filtret. Välj ”Alla aktier” för att se varför kandidater sorterats bort.", "empty");
    cell.colSpan = 5; const tr = el("tr"); tr.append(cell); body.append(tr); return;
  }
  for (const row of rows) {
    const tr = el("tr", undefined, row.symbol === state.selected ? "selected" : "");
    const symbolCell = el("td");
    const button = el("button", undefined, "symbol-button");
    button.append(el("strong", row.symbol), el("small", row.name));
    button.addEventListener("click", () => select(row.symbol).catch(e => error(e.message)));
    symbolCell.append(button); tr.append(symbolCell);
    const statusCell = el("td"); statusCell.append(badge(row)); tr.append(statusCell);
    tr.append(el("td", price(row.close)), el("td", row.relative_volume === undefined ? "—" : `${number(row.relative_volume)}×`), el("td", `${row.score || 0}`, "score"));
    body.append(tr);
  }
}
async function select(symbol) {
  state.selected = symbol; renderRows();
  const row = state.data.rows.find(r => r.symbol === symbol);
  $("#chart-symbol").textContent = symbol;
  $("#chart-name").textContent = row.name;
  $("#chart-price").textContent = row.close ? `$${price(row.close)}` : "—";
  $("#chart-status").replaceChildren(badge(row));
  $("#signal-checks").replaceChildren(...Object.entries(row.checks || {}).map(([key, passed]) => el("span", `${passed ? "✓" : "·"} ${checkLabels[key]}`, `check ${passed ? "passed" : ""}`)));
  const plan = $("#trade-plan"); plan.replaceChildren();
  for (const [label, value] of [["Entryreferens", row.entry_reference], ["Stop", row.stop], ["Mål", row.target], ["Antal aktier", row.shares], ["Planerad risk, USD", row.risk_usd], ["Relativ styrka, 63d", row.relative_strength]]) {
    const item = el("div", undefined, "plan-item");
    item.append(el("span", label), el("strong", label === "Relativ styrka, 63d" ? (value === null || value === undefined ? "—" : `${number(value*100)} pp`) : label === "Antal aktier" ? number(value, 0) : price(value)));
    plan.append(item);
  }
  const reasons = $("#candidate-reasons"); reasons.replaceChildren();
  for (const reason of row.reasons || []) reasons.append(el("p", reason));
  for (const warning of row.warnings || []) reasons.append(el("p", `△ ${warning}`, "warning"));
  state.chart = null; drawChart();
  const chart = await api(`/api/bars?symbol=${encodeURIComponent(symbol)}`);
  if (state.selected !== symbol) return;
  state.chart = chart; drawChart();
  $("#chart-readout").textContent = "Pris / volym / MACD · för pekaren över diagrammet för OHLC.";
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
  const row = state.data.rows.find(r => r.symbol === state.selected);
  if (row.resistance && row.resistance >= minPrice && row.resistance <= maxPrice) {
    ctx.strokeStyle="#ecc58a"; ctx.setLineDash([4,4]); ctx.beginPath();ctx.moveTo(left,y(row.resistance));ctx.lineTo(right,y(row.resistance));ctx.stroke();ctx.setLineDash([]);
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
$("#search").addEventListener("input",renderRows);
$("#status-filter").addEventListener("change",renderRows);
$("#refresh").addEventListener("click",refresh);
$("#settings-form").addEventListener("submit",async event => {
  event.preventDefault(); const button = event.submitter; button.disabled=true; error("");
  try {
    const values={};
    for (const input of event.target.querySelectorAll("input")) {
      if(input.type==="checkbox") values[input.name]=input.checked;
      else if (["allowed_sectors","excluded_symbols"].includes(input.name)) values[input.name]=input.value.split(",").map(v=>v.trim()).filter(Boolean).map(v=>input.name==="excluded_symbols"?v.toUpperCase():v);
      else values[input.name]=Number(input.value);
    }
    for(const key of ["min_dollar_volume","min_market_cap"])values[key]*=1e6;
    for(const key of ["risk_fraction","max_position_fraction"])values[key]/=100;
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
    const params=new URLSearchParams();for(const key of ["start","end"]){const v=$(`#backtest-${key}`).value;if(v)params.set(key,v);}
    const result=await api(`/api/backtest?${params}`);
    const body=$("#backtest-body");body.replaceChildren();
    for(const variant of result.variants){const s=variant.summary;const tr=el("tr");for(const text of [variant.name,s.trades,s.win_rate===null?"—":`${number(s.win_rate*100,1)} %`,number(s.expectancy_r),number(s.profit_factor_r),variant.open_trades])tr.append(el("td",text));body.append(tr);}
    const full=result.variants.at(-1);$("#backtest-detail").replaceChildren(...full.limitations.map(t=>el("p",t)),el("p","Kostnader och exitregler följer config.json. Profit factor visas som — om testet saknar förluster."));
    const trades=$("#trades-body");trades.replaceChildren();
    const exitLabels={stop:"Stop",stop_gap:"Gap under stop",target:"Mål",time:"Tidsgräns"};
    for(const trade of full.trades.slice(-20).reverse()){const tr=el("tr");for(const text of [trade.symbol,trade.entry_date,trade.exit_date,`$${price(trade.pnl_usd)}`,number(trade.r_multiple),exitLabels[trade.exit_reason]])tr.append(el("td",text));trades.append(tr);}
    if(!full.trades.length){const tr=el("tr");const td=el("td","Inga avslutade affärer i vald period.","empty");td.colSpan=6;tr.append(td);trades.append(tr);}
  }catch(e){error(e.message);}finally{button.disabled=false;button.textContent="Kör jämförelse";}
});
refresh();
