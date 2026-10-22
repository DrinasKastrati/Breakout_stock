"use strict";
// Strategy definitions: labels, columns and copy. The page shows one strategy at a time.
(() => {
  const list = [
    {
      id: "breakout", name: "Breakout", short: "Brk",
      eyebrow: "FRÅN UNIVERSUM TILL SETUP", title: "Hitta nästa utbrott.",
      lead: "Bekräftade signaler och aktier nära motstånd — med en förklaring till varje kandidat.",
      note: ["Pris bryter nivån.", "Volym bekräftar.", "Risk styr storleken."],
      labels: { breakout: "Breakout", watch: "Bevakning", extended: "Översträckt", inactive: "Ingen setup", excluded: "Filtrerad" },
      candidates: ["breakout", "watch"],
      filters: [["candidates", "Breakout & bevakning"], ["all", "Alla aktier"], ["breakout", "Breakout"], ["watch", "Bevakning"], ["extended", "Översträckt"], ["excluded", "Filtrerad"]],
      stats: [["breakout", "Bekräftade breakouts", "Samtliga aktiva villkor uppfyllda", "green"], ["watch", "Nära breakout", "Bevaka nästa avslutade candle", ""], ["excluded", "Filtrerade aktier", "Instrument, historik eller likviditet", ""]],
      columns: [["Kurs", "close", "price"], ["Volym ×", "relative_volume", "times"], ["Poäng", "score", "score"]],
      checks: { trend: "Trend", base: "Bas", breakout: "Pris", volume: "Volym", macd: "MACD", not_extended: "Avstånd" },
      csv: ["symbol", "date", "status", "score", "close", "resistance", "relative_volume", "entry_reference", "stop", "target", "shares", "risk_usd"],
      tableFoot: "Poängen visar uppfyllda regler. Den är ingen vinstsannolikhet."
    },
    {
      id: "metro", name: "Metro", short: "Metro",
      eyebrow: "METRO · FEM STEG", title: "Nivåer, scenarier, risk.",
      lead: "Stöd och motstånd ur swing-pivåer, köp först vid stängning över triggern och minst 2:1 i risk/reward.",
      note: ["Läget först.", "Nivån bryts.", "R/R minst 2."],
      labels: { buy: "Köp", watch: "Bevaka", sell: "Sälj", wait: "Avvakta", excluded: "Filtrerad" },
      candidates: ["buy", "watch"],
      filters: [["candidates", "Köp & bevaka"], ["all", "Alla aktier"], ["buy", "Köp"], ["watch", "Bevaka"], ["sell", "Sälj"], ["wait", "Avvakta"], ["excluded", "Filtrerad"]],
      stats: [["buy", "Köp", "Trigger, R/R och marknadsläge uppfyllda", "green"], ["watch", "Bevaka", "Nära trigger, låg R/R eller Risk-off", ""], ["sell", "Sälj", "Stängning under stöd", "pink"], ["excluded", "Filtrerade", "Instrument, historik eller likviditet", ""]],
      columns: [["Kurs", "close", "price"], ["R/R", "rr", "number"], ["Trend", "trend", "trend"]],
      checks: { trend_ok: "Trend ej bearish", trigger: "Trigger", rr_ok: "R/R ≥ 2", regime_ok: "Marknadsläge", bearish_trigger: "Under stöd" },
      csv: ["symbol", "date", "status", "close", "trend", "r1", "r2", "s1", "s2", "trigger", "t1", "t2", "stop", "rr", "shares", "risk_usd"],
      tableFoot: "Status följer fasta regler. R/R är planerad risk/reward, ingen vinstsannolikhet."
    },
    { id: "s3", name: "Strategi 3", disabled: true }
  ];
  const regimeLabels = { risk_on: "Risk-on", neutral: "Neutral", risk_off: "Risk-off" };
  const trendLabels = { bullish: "Bullish", bearish: "Bearish", sideways: "Sidledes" };
  const active = () => list.filter(s => !s.disabled);
  const get = id => active().find(s => s.id === id);
  function initial() {
    const hash = window.location.hash.slice(1);
    if (get(hash)) return hash;
    try { const saved = localStorage.getItem("breakout-strategy"); if (get(saved)) return saved; } catch (_) { /* storage blocked */ }
    return "breakout";
  }
  function remember(id) {
    if (window.location.hash.slice(1) !== id) history.replaceState(null, "", `#${id}`);
    try { localStorage.setItem("breakout-strategy", id); } catch (_) { /* storage blocked */ }
  }
  window.Strategies = { list, get, active, initial, remember, regimeLabels, trendLabels };
})();
