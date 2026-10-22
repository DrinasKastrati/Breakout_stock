# Metro-strategin och strategibyte — implementationsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lägga till Metro som andra strategi bredvid breakout, med strategibyte enligt upplägg B, utan att breakoutens resultat ändras.

**Architecture:** Metro byggs som platta moduler i `breakout_lab/` (nivåer, marknadsläge, utvärdering, kontext), kopplas in i befintlig scan-, backtest- och sitekedja via tillägg i payloaden (`strategies.metro`) och ett generaliserat `simulate_trade`. Frontenden får ett strategireglage; grafen ritar bara aktiv strategis `chart_levels`.

**Tech Stack:** Python 3.11–3.13 standardbibliotek + befintliga beroenden (`cryptography`), `unittest`, vanilla JS + canvas.

**Spec:** `docs/superpowers/specs/2026-10-22-metro-strategi-design.md` — läs den. Paragrafhänvisningar (§) nedan avser den.

## Global Constraints

- Breakoutens rader, räkningar och backtest ska vara identiska före och efter (golden-test, Task 1).
- Nya Python-moduler ligger **platt** i `breakout_lab/`. `pages.static_hash` hashar bara `breakout_lab/*.py` och `static/*`; en underkatalog skulle göra att kodändringar inte tvingar ny publicering.
- Inga nya pip-beroenden. HTTP via `urllib` som i `providers.py`.
- Kausalitet: signal vid `t` använder bara data känd vid `t`:s stängning; pivå vid `j` är känd först vid `j + pivot_span`.
- Inga betal-API:er (ägarens beslut). Alla riktiga data och nyheter hamnar bara i krypterade payloads. Ingen nyckel, inget svarsinnehåll i felmeddelanden.
- Extern text (scout-rapport, rubriker, sammanfattningar) renderas med `textContent`, aldrig `innerHTML`.
- Statusnycklar Metro: `buy`, `watch`, `sell`, `wait`, `excluded`. Svenska etiketter: Köp, Bevaka, Sälj, Avvakta, Filtrerad.
- Regimnycklar: `risk_on`, `neutral`, `risk_off`. Etiketter: Risk-on, Neutral, Risk-off.
- Metro-parametrar (§5), förval: `pivot_span=5`, `level_lookback=250`, `cluster_atr=0.5`, `trigger_atr_buffer=0.1`, `stop_atr=1.0`, `min_rr=2.0`, `watch_distance_atr=1.0`, `breadth_risk_on=0.5`, `breadth_risk_off=0.4`, `use_regime=True`, `shortlist_size=20`, `news_days=3`.
- Testkommando (Windows kräver UTF-8-läge): `PYTHONUTF8=1 python -m unittest discover -s tests`. **Känd baslinje:** 99 tester, 2 befintliga Windows-fel i `test_data_and_api` (`tearDownClass (test_data_and_api.API)`, `test_refresh_rolls_back_invalid_dataset`, låst temporär SQLite-fil). De räknas inte som regressioner; alla andra ska passera. På Linux/CI ska allt passera.
- Commit-meddelanden avslutas med `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Pusha inte; ägaren beslutar om push (push till `main` startar Pages-workflow).

## Review Focus

1. **Aktie på all time high** (ingen nivå över `close[t-1]`): ska bli `wait` med orsak "Motståndsnivå saknas", aldrig krasch eller köp. Test i Task 5.
2. **Index saknas eller har < 200 candles** (kort `--years`, demo utan SPY): marknadsläge `neutral` med not "Indexhistorik saknas", ingen krasch. Test i Task 4.
3. **`config.json` utan `metro`-block** (forskningsworkflows, äldre filer): förval används, forskningsmodulerna laddar som förut. Test i Task 2.
4. **Nätverksfel, HTTP-fel eller trasig JSON från Alpaca News eller GitHub raw**: publiceringen fortsätter, panelen visar "ej tillgängligt". Tester i Task 9.
5. **Extern text med HTML/script** (rubrik `<img onerror=…>`): visas som text. Test i Task 9 (Python behåller som sträng) och grep-kontroll i Task 11.

---

### Task 1: Golden-fixtur för breakouten

**Files:**
- Create: `tests/golden_breakout.py` (genererar fixturen)
- Create: `tests/golden/breakout_demo.json`
- Create: `tests/test_breakout_unchanged.py`

**Interfaces:**
- Produces: `tests/golden/breakout_demo.json` = `{"scan": {"rows": [...], "counts": {...}}, "compare": [...]}` från demodatan och repots `config.json`. Senare tasks ändrar den **aldrig**.

- [ ] **Step 1:** Skriv `tests/golden_breakout.py` med `def snapshot() -> dict`: `assets, histories, meta = demo.dataset()`, `config = Config.from_dict(json.loads(Path("config.json").read_text(encoding="utf-8")))`, benchmark-dict ur `meta["benchmark_symbol"]`, `rows = scan(...)`, counts för `breakout, watch, extended, inactive, excluded`, `compare(assets, histories, config)`. Returnera JSON-rundtrippat (`json.loads(json.dumps(..., allow_nan=False))`). `if __name__ == "__main__":` skriver `tests/golden/breakout_demo.json` (indent=1, sort_keys=True).
- [ ] **Step 2:** Kör `PYTHONUTF8=1 python tests/golden_breakout.py` från repo-roten **innan någon annan kod ändras**. Förväntat: filen skapas.
- [ ] **Step 3:** Skriv `tests/test_breakout_unchanged.py`:

```python
class BreakoutUnchanged(unittest.TestCase):
    def test_demo_scan_and_backtest_match_golden(self):
        expected = json.loads(Path(__file__).with_name("golden").joinpath("breakout_demo.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot(), expected)
```

- [ ] **Step 4:** Kör hela sviten. Förväntat: 100 tester, bara de 2 kända Windows-felen.
- [ ] **Step 5:** Commit `test: freeze breakout demo output before Metro work`.

---

### Task 2: `MetroConfig` i konfigurationen

**Files:**
- Modify: `breakout_lab/models.py`
- Modify: `config.json`
- Modify: `breakout_lab/server.py` (`Application.update_config`)
- Test: `tests/test_metro_config.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) class MetroConfig` med fälten i Global Constraints (typer: `pivot_span:int`, `level_lookback:int`, `shortlist_size:int`, `news_days:int`, `use_regime:bool`, övriga `float`); `MetroConfig.from_dict(data: dict) -> MetroConfig` (avvisar okända nycklar och negativa/icke-ändliga värden, kräver `pivot_span ≥ 1`, `level_lookback > 2*pivot_span`, `0 ≤ breadth_risk_off ≤ breadth_risk_on ≤ 1`, `min_rr > 0`).
- Produces: `Config.metro: MetroConfig = field(default_factory=MetroConfig)`. `Config.from_dict` bygger `metro` via `MetroConfig.from_dict(values.get("metro", {}))` och hoppar över `metro` i den numeriska valideringsloopen. `Config.to_dict()["metro"]` är en dict.

- [ ] **Step 1: Failing tests**

```python
def test_missing_metro_block_uses_defaults(self):
    c = Config.from_dict({"lookback": 20})
    self.assertEqual(c.metro, MetroConfig())
    self.assertEqual(c.metro.min_rr, 2.0)
def test_repo_config_loads_and_roundtrips(self):
    c = Config.from_dict(json.loads(Path("config.json").read_text(encoding="utf-8")))
    self.assertEqual(Config.from_dict(c.to_dict()), c)
    self.assertIsInstance(c.to_dict()["metro"], dict)
def test_unknown_metro_key_rejected(self):
    with self.assertRaises(ValueError): Config.from_dict({"metro": {"bogus": 1}})
def test_invalid_breadth_order_rejected(self):
    with self.assertRaises(ValueError): Config.from_dict({"metro": {"breadth_risk_on": 0.3, "breadth_risk_off": 0.4}})
def test_replace_keeps_metro(self):
    c = Config.from_dict({"metro": {"min_rr": 3.0}})
    self.assertEqual(replace(c, account_equity=5).metro.min_rr, 3.0)
def test_server_update_preserves_metro(self):
    app = Application(store=None, config=Config.from_dict({"metro": {"min_rr": 3.0}}))
    self.assertEqual(app.update_config({"min_price": 6}).metro.min_rr, 3.0)
    self.assertEqual(app.update_config({"metro": {**asdict(MetroConfig()), "min_rr": 2.5}}).metro.min_rr, 2.5)
```

- [ ] **Step 2:** Kör `PYTHONUTF8=1 python -m unittest tests.test_metro_config -v`. Förväntat: FAIL (`MetroConfig` saknas).
- [ ] **Step 3:** Implementera i `models.py`. `update_config` ska fungera oförändrat tack vare `to_dict`/`from_dict`; ändra bara om testet kräver det. Lägg till `"metro": {...}` med alla förval i `config.json`.
- [ ] **Step 4:** Kör nya testerna + hela sviten (golden ska passera).
- [ ] **Step 5:** Commit `feat: add Metro settings block to config`.

---

### Task 3: SMA 200, pivåer och nivåer

**Files:**
- Modify: `breakout_lab/indicators.py` (`calculate` får nyckeln `sma200`)
- Create: `breakout_lab/metro_levels.py`
- Test: `tests/test_metro_levels.py`

**Interfaces:**
- Produces: `calculate(bars)["sma200"]` (samma form som `sma50`).
- Produces: `find_pivots(bars: list[Bar], span: int) -> list[tuple[int, str, float]]` — `(index, "high"|"low", price)`, sorterad på index; high-pivå när `high[j]` är **strikt** större än alla andra highs i `[j-span, j+span]` (spegelvänt för low); bara `j` med hela fönstret inom `bars`.
- Produces: `known_pivots(pivots, t: int, span: int, lookback: int) -> list[tuple]` — de med `j + span <= t - 1` och `j >= t - 1 - lookback`.
- Produces: `cluster_levels(prices: list[float], width: float) -> list[dict]` — `[{"price": float, "touches": int}]` stigande; förankrad sammanslagning (§5.1).
- Produces: `nearest_levels(levels: list[dict], reference: float) -> dict` — nycklar `r1, r2, r3, s1, s2` (pris eller `None`); `r*` strikt över, `s*` strikt under `reference`, närmast först.

- [ ] **Step 1: Failing tests**

```python
def test_pivot_is_known_only_after_span(self):
    highs = [1, 2, 3, 9, 3, 2, 1, 1]
    bars = [Bar(f"2024-01-{i+1:02}", h, h, h - .5, h - .25, 1000) for i, h in enumerate(highs)]  # low < open/close
    p = find_pivots(bars, 2)
    self.assertIn((3, "high", 9), p)
    self.assertEqual(known_pivots(p, t=5, span=2, lookback=250), [])      # 3+2 > 4
    self.assertIn((3, "high", 9), known_pivots(p, t=6, span=2, lookback=250))
def test_equal_highs_are_not_pivots(self): ...  # två lika toppar i samma fönster -> ingen high-pivå
def test_cluster_is_anchored_not_chained(self):
    self.assertEqual(cluster_levels([10.0, 10.3, 10.6, 12.0], 0.5),
                     [{"price": 10.15, "touches": 2}, {"price": 10.6, "touches": 1}, {"price": 12.0, "touches": 1}])
def test_nearest_levels(self):
    lv = [{"price": p, "touches": 1} for p in (8, 9, 11, 12, 13)]
    self.assertEqual(nearest_levels(lv, 10), {"r1": 11, "r2": 12, "r3": 13, "s1": 9, "s2": 8})
    self.assertEqual(nearest_levels(lv, 14)["r1"], None)
def test_future_bars_do_not_change_known_pivots(self): ...  # find_pivots på bars[:200] vs bars[:260], known_pivots vid t=199 identiska
def test_sma200_causal(self): ...  # calculate(bars[:220])["sma200"] == calculate(bars)["sma200"][:220]
```

Använd `assertAlmostEqual` för medelpriset om flyttal kräver det.

- [ ] **Step 2:** Kör, förväntat FAIL (modul saknas).
- [ ] **Step 3:** Implementera. `cluster_levels`: sortera stigande, starta kluster vid första pris, lägg till så länge `price - cluster_first <= width`, annars nytt kluster.
- [ ] **Step 4:** Kör nya + hela sviten (golden passerar; `sma200` ändrar inte breakouten).
- [ ] **Step 5:** Commit `feat: add causal swing pivots and anchored level clustering`.

---

### Task 4: Marknadsläge (bredd + index)

**Files:**
- Modify: `breakout_lab/engine.py` — bryt ut `eligibility`
- Create: `breakout_lab/metro_regime.py`
- Test: `tests/test_metro_regime.py`

**Interfaces:**
- Produces (engine): `eligibility(asset, bars, i, config, historical=False, require_history=True) -> tuple[list[str], float | None]` — exakt de orsaker `evaluate` ger före ATR-steget och snittdollaromsättningen. Ordningen bevaras: först universum + `min_history` + prisgräns; dollaromsättningen kontrolleras **bara** om dessa inte gav någon orsak (som i dag). `evaluate` anropar den; beteendet oförändrat (golden). `require_history=False` hoppar över `min_history` (bredden kräver den inte, §5.4) men kräver fortfarande `i >= config.lookback`, annars orsak `f"Kräver {config.lookback} candles"` — annars blir `bars[i-lookback:i]` en felaktig negativ slice.
- Produces: `breadth_by_date(assets, histories, config, indicators: dict[str, dict], historical: bool, dates: set[str] | None = None) -> dict[str, tuple[int, int]]` — datum → `(över_sma50, behöriga)`; behörig = `eligibility(..., require_history=False)` ger inga orsaker och `sma50[i]` finns.
- Produces: `regime_series(benchmark: list[Bar], breadth: dict, metro: MetroConfig) -> dict[str, dict]` — datum → `{"date", "label", "index_close", "index_sma200", "breadth", "eligible", "notes": list[str]}`; regler §5.4; saknad SMA200 eller `eligible == 0` → `neutral` med not "Indexhistorik saknas" respektive "Inga behöriga aktier".

- [ ] **Step 1: Failing tests** — konstruera index med 250 stigande candles (SMA200 under kurs) och små aktieuppsättningar:

```python
def test_risk_on_needs_index_above_sma200_and_breadth_at_least_half(self): ...   # 2 av 4 över -> risk_on
def test_risk_off_needs_index_below_and_breadth_below_40(self): ...              # fallande index, 1 av 4 -> risk_off
def test_mixed_is_neutral(self): ...                                              # index över, 1 av 4 -> neutral
def test_short_index_history_is_neutral_with_note(self):
    r = regime_series(index_bars[:150], breadth, MetroConfig())
    last = r[index_bars[149].date]
    self.assertEqual(last["label"], "neutral"); self.assertIn("Indexhistorik saknas", last["notes"])
def test_illiquid_stock_not_in_denominator(self): ...  # aktie under min_dollar_volume räknas inte i eligible
def test_evaluate_unchanged_after_refactor(self): ...  # täcks av golden; inget extra test krävs
```

- [ ] **Step 2:** Kör, FAIL.
- [ ] **Step 3:** Implementera. `dates` begränsar beräkningen (live behöver bara `as_of`; backtest alla).
- [ ] **Step 4:** Kör nya + hela sviten.
- [ ] **Step 5:** Commit `feat: add mechanical market regime from index trend and breadth`.

---

### Task 5: Metro-utvärdering och scan

**Files:**
- Create: `breakout_lab/metro.py`
- Test: `tests/test_metro.py`

**Interfaces:**
- Consumes: Task 3 (`find_pivots`, `known_pivots`, `cluster_levels`, `nearest_levels`), Task 4 (`eligibility`, regime-dict), `engine.position_plan`, `indicators.calculate`.
- Produces: `METRO_STATUSES = ("buy", "watch", "sell", "wait", "excluded")`.
- Produces: `evaluate_metro(asset, bars, config, index=None, indicators=None, pivots=None, regime=None, historical=False) -> dict` med nycklar: `symbol, name, sector, date, close, status, reasons, warnings, trend ("bullish"|"bearish"|"sideways"), r1, r2, s1, s2, trigger, t1, t2, bear_trigger, bear_t1, bear_t2, stop, rr, atr, entry_reference, shares, risk_usd, target, regime, checks, chart_levels`. `bear_trigger = s1 - trigger_atr_buffer * ATR_prev`; `bear_t1 = s2`, annars `s1 - (r1 - s1)`; `bear_t2 = s1 - 2*(r1 - s1)` (bara visning, §5.3). `checks = {"trend_ok", "trigger", "rr_ok", "regime_ok", "bearish_trigger"}` (bool). `chart_levels = [{"kind": "s2"|"s1"|"r1"|"r2"|"t1"|"t2"|"stop", "price": float, "label": str}]`, bara existerande nivåer. `regime=None` → behandlas som `neutral` + varning "Marknadsläge saknas". `target == t1`.
- Produces: `scan_metro(assets, histories, config, regimes: dict[str, dict], as_of=None) -> list[dict]` — sorterad: `buy`, `watch`, `sell`, `wait`, `excluded`; inom status `rr` fallande (None sist), sedan symbol. Saknad sessionscandle → `excluded` med "Senaste avslutade handelssessionen saknas" (som `engine.scan`).

Regler exakt enligt §5.1–5.4. Följande avgör det som §5 lämnar öppet:
- `ATR_prev = indicators["atr"][i-1]`; saknas/≤0 → `excluded`, "ATR saknas eller är noll".
- Nivåer: `cluster_levels([p for _, _, p in known], metro.cluster_atr * ATR_prev)`, referens `close[i-1]`.
- Trend: två senaste kända low-pivåer (`known`, kind `"low"`) stigande respektive två senaste high-pivåer fallande; SMA50/SMA200 vid `i`.
- `trigger = r1 + trigger_atr_buffer * ATR_prev`. T1 = r2, annars `r1 + (r1 - s1)`. T2 = r3, annars `r1 + 2*(r1 - s1)`; T2 sätts till `None` om den inte är > T1. Utan `s1` och utan `r2`: T1 = `None` → ingen `buy`, orsak "Mål saknas".
- `stop = r1 - stop_atr * ATR_prev`; `rr = (t1 - close) / (close - stop)` när `close > stop` och `t1` finns, annars `None`.
- `regime_ok = not metro.use_regime or regime["label"] != "risk_off"`.
- `shares, risk_usd` ur `position_plan(close, stop, config)`; dess `target` skrivs över med T1.
- Orsakstexter (exakt): "Motståndsnivå saknas", "Stödnivå saknas", "Bearish trend", "Ingen stängning över triggern", `f"R/R {rr:.1f} under kravet {min_rr:g}"`, "Risk-off: köpsignal nedgraderad", "Stängning under stöd: sälj om du äger, undvik annars", "Inom intervallet: avvakta bekräftelse", "Samtliga Metro-villkor uppfyllda". Decimaltecken i UI hanteras av frontenden; Python-texten använder punkt.

- [ ] **Step 1: Failing tests** — skriv en testhjälpare `zigzag(points: list[tuple[int, float]], length: int) -> list[Bar]` som linjärt interpolerar stängningar mellan givna (index, pris), sätter `high = close*1.002`, `low = close*0.998`, `open = föregående close`, volym 2 000 000 (klarar likviditet vid pris ≥ 10). Tester:

```python
def test_buy_on_close_above_trigger_with_rr_at_least_two(self): ...      # status "buy", checks alla sanna, t1 == r2
def test_low_rr_becomes_watch_with_reason(self): ...                       # r2 nära r1 -> "watch", reason startar "R/R "
def test_risk_off_downgrades_buy_to_watch(self): ...                       # regime={"label":"risk_off",...} -> "watch", "Risk-off: köpsignal nedgraderad"
def test_risk_off_ignored_when_use_regime_false(self): ...                 # replace(config, metro=replace(config.metro, use_regime=False)) -> "buy"
def test_close_below_support_is_sell(self): ...
def test_all_time_high_without_resistance_is_wait(self):
    r = evaluate_metro(asset, ath_bars, config, regime=NEUTRAL)
    self.assertEqual(r["status"], "wait"); self.assertIn("Motståndsnivå saknas", r["reasons"])
def test_measured_move_target_when_r2_missing(self): ...                  # t1 == r1 + (r1 - s1)
def test_future_bars_do_not_change_result_at_t(self):
    a = evaluate_metro(asset, bars[:400], config, regime=NEUTRAL)
    b = evaluate_metro(asset, bars, config, index=399, indicators=calculate(bars), regime=NEUTRAL)
    for k in ("status", "r1", "s1", "t1", "stop", "rr"): self.assertEqual(a[k], b[k])
def test_chart_levels_only_existing_levels(self): ...
def test_scan_sorting_and_missing_session(self): ...
```

`NEUTRAL = {"label": "neutral", "notes": []}` i testerna.

- [ ] **Step 2:** Kör, FAIL.
- [ ] **Step 3:** Implementera.
- [ ] **Step 4:** Kör nya + hela sviten.
- [ ] **Step 5:** Commit `feat: evaluate Metro levels, scenarios and status per stock`.

---

### Task 6: Generaliserat backtest + Metro-varianter

**Files:**
- Modify: `breakout_lab/backtest.py`
- Test: `tests/test_metro_backtest.py`

**Interfaces:**
- Consumes: Task 4 (`breadth_by_date`, `regime_series`), Task 5 (`evaluate_metro`), Task 3 (`find_pivots`).
- Produces: `breakout_plan(entry, candidate, config) -> dict | None` — nuvarande logik ur `simulate_trade` (avstå vid `entry <= stop` eller över `resistance + max_extension_atr*atr`; `position_plan`; `None` om `shares < 1`); returnerar `{"shares", "target"}`.
- Produces: `metro_plan(entry, candidate, config) -> dict | None` — avstå vid `entry <= stop`, `t1 is None`, eller `(t1 - entry)/(entry - stop) < metro.min_rr`; `shares` ur `position_plan`, `target = t1`.
- Produces: `simulate_trade(bars, signal_index, candidate, config, plan=breakout_plan)` — exitlogik oförändrad.
- Produces: `backtest(assets, histories, config, start=None, end=None, *, evaluator=None, signal="breakout", plan=breakout_plan, limitations=None)`; `evaluator(asset, bars, i, ind) -> dict`, förval `evaluate(asset, bars, config, i, ind, historical=True)`.
- Produces: `compare_metro(assets, histories, config, start=None, end=None) -> list[dict]` — varianter `"Metro"` (`use_regime=True`) och `"Metro utan regimfilter"` (`use_regime=False`), samma form som `compare`. Regim beräknas en gång med `historical=True`; pivåer cachas per symbol.
- Metro-`limitations` = breakoutens tre texter + "Affärer i olika aktier överlappar i tid; antalet affärer är inte antalet oberoende observationer." + "Bredden räknas på dagens universum och bär överlevnadsbias bakåt." + "Visning, inte bevis: fönstret flyttas dagligen och ses löpande."

- [ ] **Step 1: Failing tests**

```python
def test_metro_plan_rejects_entry_with_low_rr(self):
    c = {"stop": 9.0, "t1": 11.0}
    self.assertIsNone(metro_plan(10.5, c, Config()))   # (11-10.5)/(10.5-9) = 0.33
    self.assertEqual(metro_plan(9.5, c, Config())["target"], 11.0)   # 1.5/0.5 = 3
def test_metro_trade_exits_at_t1(self): ...        # syntetisk serie, signal -> exit_reason "target", exit == t1*(1-slip)
def test_compare_metro_has_two_named_variants(self):
    names = [v["name"] for v in compare_metro(*demo_inputs())]
    self.assertEqual(names, ["Metro", "Metro utan regimfilter"])
def test_metro_limitations_say_not_evidence(self): ...  # "Visning, inte bevis" finns i limitations
```

- [ ] **Step 2:** Kör, FAIL.
- [ ] **Step 3:** Implementera. Golden-testet bevisar att breakouten inte ändrats.
- [ ] **Step 4:** Kör nya + hela sviten.
- [ ] **Step 5:** Commit `feat: generalize trade simulation and add Metro backtest variants`.

---

### Task 7: Koppla in Metro i scan-payload, API, CLI och statisk klient

**Files:**
- Create: `breakout_lab/strategies.py`
- Modify: `breakout_lab/pages.py` (`export_site`), `breakout_lab/server.py`, `breakout_lab/cli.py`, `breakout_lab/static/data-client.js`
- Test: `tests/test_strategies.py`, utöka `tests/test_pages.py`

**Interfaces:**
- Produces: `STRATEGIES = ({"id": "breakout", "name": "Breakout"}, {"id": "metro", "name": "Metro"})`.
- Produces: `metro_section(assets, histories, config, metadata, context_builder=None) -> dict` — `{"rows", "counts", "regime", "context"}`; `counts` över `METRO_STATUSES`; `regime` = regimen för `metadata["as_of"]` (beräknad med `dates={as_of}`); `context = context_builder(rows, regime)` om given, i try/except — fel ger `None` och publiceringen fortsätter. (En builder i stället för färdig kontext, eftersom kontexten behöver Metro-raderna och regimen som räknas här.)
- Produces (scan-payload): befintliga nycklar oförändrade (breakoutens `rows`, `counts` ligger kvar på toppnivå — dubblera dem inte) + `"strategies": {"metro": metro_section(...)}`.
- Produces (backtest-payload): befintligt + `"strategies": {"metro": {"variants": compare_metro(...)}}` (affärer trunkeras till senaste 100 per variant som för breakout). Fel → `{"error": str}` under `strategies.metro`.
- Produces (lokalt API): `/api/scan` samma form; `/api/backtest?strategy=metro` → `{"variants": [...], "metadata"}`; `/api/export?strategy=metro` med kolumner `symbol,date,status,close,trend,r1,r2,s1,s2,trigger,t1,t2,stop,rr,shares,risk_usd`, filnamn `metro-scan.csv`.
- Produces (CLI): `scan --strategy {breakout,metro}` och `backtest --strategy {breakout,metro}`, förval `breakout`.
- Produces (statisk klient): `request("/api/backtest?strategy=metro")` returnerar `backtest.strategies.metro`; `exportCSV(rows, columns, filename)`.
- `export_site(..., context_builder=None)` — ny parameter, skickas till `metro_section`.

- [ ] **Step 1: Failing tests**

```python
def test_demo_payload_has_metro_section(self):
    scan = self.read_payload("scan")
    self.assertEqual(set(scan["strategies"]["metro"]["counts"]), {"buy","watch","sell","wait","excluded"})
    self.assertEqual(len(scan["strategies"]["metro"]["rows"]), len(scan["rows"]))
    self.assertIn(scan["strategies"]["metro"]["regime"]["label"], {"risk_on","neutral","risk_off"})
def test_demo_backtest_payload_has_metro_variants(self): ...
def test_local_api_backtest_strategy_param(self): ...   # i test_data_and_api-stil: GET /api/backtest?strategy=metro -> 2 varianter
def test_cli_scan_metro(self): ...                       # main(["--db", tmp, "scan", "--strategy", "metro"]) == 0
```

Följ befintliga hjälpare i `tests/test_pages.py` för att läsa demopayloads.

- [ ] **Step 2:** Kör, FAIL.
- [ ] **Step 3:** Implementera. Utöka sökvägsregexen i `pages.decrypt_file` och `data-client.js` bara om nya payloadfiler tillkommer (planen lägger allt i befintliga `scan`/`backtest`, så det ska inte behövas; bekräfta).
- [ ] **Step 4:** Kör nya + hela sviten. Kör `PYTHONUTF8=1 python -m breakout_lab build-site --source demo --output dist/site-check` → exit 0.
- [ ] **Step 5:** Commit `feat: publish Metro rows, regime and backtest alongside breakout`.

---

### Task 8: Nyhetsreaktion (gratis sentiment)

**Files:**
- Create: `breakout_lab/reaction.py`
- Test: `tests/test_reaction.py`

**Interfaces:**
- Produces: `reaction_day(created_at: str, sessions: list[str]) -> str | None` — `created_at` RFC-3339; omvandla till New York-tid; om datumet är en session i `sessions` och klockan är före 16:00 → det datumet, annars första session strikt efter datumet. Ingen sådan session (efter sista i listan) → `None`.
- Produces: `day_reaction(bars: list[Bar], index_bars: dict[str, float], day: str) -> dict | None` — `{"day", "excess", "rvol", "label"}`; `excess = close[d]/close[d-1] - 1 - (index[d]/index[d-1] - 1)`; `rvol = volume[d] / medel(volume[d-20:d])`; `label`: `"positive"` om `excess >= 0.02` och `rvol >= 1.5`, `"negative"` om `excess <= -0.02` och `rvol >= 1.5`, annars `"none"`. Saknas dagen, föregående dag, indexvärde eller 20 föregående candles → `None`.
- Produces: `symbol_reactions(articles: list[dict], bars: list[Bar], index_bars: dict[str, float]) -> dict` — `{"articles": [artikel + {"reaction_day", "reaction"}], "summary": {"label", "day", "excess", "rvol"} | {"label": "none"}}`; `reaction` = `day_reaction(...)` eller `None` (visas "Reaktion okänd än"); summary = senaste reaktionsdag med `label != "none"`, annars `{"label": "none"}`.
- Trösklar (§5.6) som modulkonstanter: `EXCESS_THRESHOLD = 0.02`, `RVOL_THRESHOLD = 1.5`, `VOLUME_LOOKBACK = 20`. Inte i `config.json` — de är fastställda före data.

- [ ] **Step 1: Failing tests**

```python
def test_before_close_is_same_session(self):
    self.assertEqual(reaction_day("2026-10-20T14:00:00Z", ["2026-10-19", "2026-10-20", "2026-10-21"]), "2026-10-20")  # 10:00 NY
def test_after_close_is_next_session(self):
    self.assertEqual(reaction_day("2026-10-20T21:30:00Z", ["2026-10-20", "2026-10-21"]), "2026-10-21")                 # 17:30 NY
def test_weekend_goes_to_next_session(self): ...          # lördag -> måndag
def test_after_last_session_is_unknown(self):
    self.assertIsNone(reaction_day("2026-10-21T21:30:00Z", ["2026-10-20", "2026-10-21"]))
def test_thresholds_are_inclusive(self): ...              # excess exakt 0.02 och rvol exakt 1.5 -> "positive"
def test_big_move_without_volume_is_none(self): ...       # excess 0.05, rvol 1.2 -> "none"
def test_negative_reaction(self): ...
def test_missing_history_returns_none(self): ...          # < 20 föregående candles
def test_summary_uses_latest_clear_reaction(self): ...
```

Använd `assertAlmostEqual` för `excess`/`rvol`; konstruera gränsfallen med marginal 1e-9 på rätt sida om flyttal kräver det.

- [ ] **Step 2:** Kör, FAIL.
- [ ] **Step 3:** Implementera (`zoneinfo` som i `providers.py`).
- [ ] **Step 4:** Kör nya + hela sviten.
- [ ] **Step 5:** Commit `feat: classify market reaction to news without paid APIs`.

---

### Task 9: Kontext — marknadsberättelse, nyheter, kortlista, logg

**Files:**
- Create: `breakout_lab/context.py`
- Modify: `breakout_lab/providers.py` (`Alpaca.news`), `breakout_lab/pages.py` (`build_site`)
- Test: `tests/test_context.py`

**Interfaces:**
- Consumes: Task 8 (`symbol_reactions`), Task 7 (`export_site(context_builder=...)`).
- Produces: `Alpaca.news(symbols: list[str], start: str, end: str) -> dict[str, list[dict]]` — `GET https://data.alpaca.markets/v1beta1/news` med `symbols`, `start`, `end`, `limit=50`, `sort=desc`, paginering med `page_token`, högst 5 sidor; artikel = `{"headline", "summary", "created_at", "source", "url"}`; varje artikel läggs under varje symbol i `symbols` som den nämner; högst 5 per symbol. Fel → `ValueError` utan svarsinnehåll (som `get`).
- Produces: `shortlist(rows: list[dict], size: int) -> list[str]` — `buy` plus `watch` med `checks["trigger"]`, sorterade `rr` fallande, högst `size`.
- Produces: `scout_narrative(as_of: str, opener=urlopen) -> dict | None` — prova `https://raw.githubusercontent.com/DrinasKastrati/Vecko_agent/main/reports/scout/rapport-{yymmdd}.md` för `as_of`+1, `as_of`, `as_of`−1, `as_of`−2, `as_of`−3 (nyast först; äldre än 3 kalenderdagar visas inte, §5.6); timeout 10 s per anrop; första träff vinner. Extrahera avsnittet från raden som börjar med `## Marknadsöversikt` till nästa rad som börjar med `## `; behåll texten oförändrad (markdown som ren text), trunkera till 4000 tecken. Returnera `{"date": "YYYY-MM-DD", "text": str, "url": str}`; saknat avsnitt eller allt fel → `None`.
- Produces: `build_context(rows, as_of, metro, histories, benchmark_symbol, news_client=None, opener=urlopen, previous_log=None) -> dict` — `{"shortlist": [...], "narrative": dict|None, "news": {"available": bool, "note": str, "by_symbol": {symbol: symbol_reactions(...)}}, "log": [...]}`. Nyheter från `as_of − (news_days + 2)` kalenderdagar till `as_of` (ungefär `news_days` handelsdagar). `news_client=None` → `available False`, note "Demodata har inga nyheter."; fel från `news_client` → `available False`, note "Nyheter ej tillgängliga". `opener=None` → narrativ `None` utan nätanrop.
- Produces: `merge_log(previous: list[dict], entries: list[dict], max_entries: int = 10000) -> list[dict]` — post `{"date", "symbol", "status", "rr", "reaction", "excess", "rvol"}` (ur `summary`); nyckel `(date, symbol)`, nya ersätter gamla, sorterad på `(date, symbol)`, behåll de senaste `max_entries`.
- `build_site` (alpaca): efter datahämtning, läs föregående scan via `decrypt_file` i ett eget try-block (oberoende av genvägen) för `strategies.metro.context.log`; fel → `[]` och not i `metadata["notes"]`: "Reaktionsloggen startade om (föregående snapshot kunde inte läsas)." Skicka `context_builder=lambda rows, regime: build_context(rows, as_of, config.metro, histories, "SPY", news_client=client, previous_log=log)` till `export_site`. Fel i kontextdelen fångas (Task 7); publiceringen fortsätter.
- `build_site` (demo): `context_builder=lambda rows, regime: build_context(rows, as_of, config.metro, histories, metadata["benchmark_symbol"], news_client=None, opener=None)`.
- `.github/workflows/pages.yml` ändras inte (inga nya secrets).

- [ ] **Step 1: Failing tests** (inga riktiga nätanrop; `opener`-stubbar som i befintliga Alpaca-tester)

```python
def test_shortlist_prefers_buy_then_triggered_watch_by_rr(self): ...
def test_narrative_extracts_marknadsoversikt_section(self): ...    # stubbad markdown med två ##-avsnitt
def test_narrative_none_when_all_fetches_fail(self): ...           # opener kastar URLError
def test_narrative_too_old_is_ignored(self): ...                   # bara fil för as_of-4 finns -> None
def test_news_http_error_marks_unavailable_and_does_not_raise(self): ...
def test_news_keeps_markup_as_plain_string(self):
    ctx = build_context(rows, as_of, MetroConfig(), histories, "IDX", news_client=stub_with_headline("<img src=x onerror=alert(1)>"), opener=None)
    self.assertEqual(ctx["news"]["by_symbol"]["AAA"]["articles"][0]["headline"], "<img src=x onerror=alert(1)>")
def test_only_shortlisted_symbols_are_requested(self): ...         # stubben registrerar symbols-argumentet
def test_merge_log_dedupes_and_bounds(self): ...
def test_export_survives_context_builder_failure(self): ...         # context_builder kastar -> export lyckas, strategies.metro.context is None
```

- [ ] **Step 2:** Kör, FAIL.
- [ ] **Step 3:** Implementera.
- [ ] **Step 4:** Kör nya + hela sviten.
- [ ] **Step 5:** Commit `feat: add Metro context with scout narrative, news reactions and log`.
- [ ] **Step 6 (manuell, ägaren):** När nycklar finns lokalt: `PYTHONUTF8=1 python -c "from breakout_lab.providers import Alpaca; print(len(Alpaca().news(['AAPL'], '2026-10-15', '2026-10-21').get('AAPL', [])))"`. Ett tal ≥ 0 utan fel betyder att nyhets-API:t ingår i planen. HTTP 403 betyder att det inte gör det — då står "Nyheter ej tillgängliga" och inget annat behöver ändras. Rapportera utfallet i överlämningen; påstå inte att det fungerar utan körningen.

---

### Task 10: Frontend — reglage, siffror, lista, CSV

**Files:**
- Create: `breakout_lab/static/strategies.js` (strategidefinitioner: id, namn, accent, statusetiketter, siffror, tabellkolumner, CSV-kolumner)
- Modify: `breakout_lab/static/index.html`, `breakout_lab/static/app.js`, `breakout_lab/static/style.css`, `breakout_lab/server.py` (lägg `/strategies.js` i de tillåtna statiska sökvägarna i `do_GET` och `do_HEAD`)

**Interfaces:**
- Consumes: scan-payload från Task 7.
- Produces: `window.Strategies = { list, get(id), active(), setActive(id) }`; aktiv strategi i `state.strategy`; `rowsFor(id)` returnerar `state.data.rows` för breakout och `state.data.strategies.metro.rows` för Metro; `statusFor(id, symbol)`.
- Reglage i toppfältet: `Breakout | Metro | Strategi 3` (sista `disabled`, title "Kommer"). Hash `#breakout`/`#metro` styr och uppdateras; `localStorage` (try/catch) som reserv. `body[data-strategy]` sätter accent: breakout `#8badff`, Metro `#b392f0`.
- Siffror: Metro visar Köp, Bevaka, Sälj, Filtrerad + marknadslägesbricka (etikett + bredd i %). Breakout oförändrat.
- Lista: aktiv strategis kolumner (Metro: Aktie, Status, Kurs, R/R, Trend) + en smal kolumn per övrig strategi med kort statusbricka. Statusfiltret byggs om per strategi (Metro: "Köp & bevaka", Alla, Köp, Bevaka, Sälj, Avvakta, Filtrerad).
- CSV: `exportCSV(rows, columns, filename)` med aktiv strategis kolumner.

- [ ] **Step 1:** Implementera.
- [ ] **Step 2:** `node --check breakout_lab/static/app.js && node --check breakout_lab/static/strategies.js` → inga fel.
- [ ] **Step 3:** Kör hela Python-sviten (statiska filer ingår i `static_hash`/pages-tester).
- [ ] **Step 4:** `PYTHONUTF8=1 python -m breakout_lab demo` och `python -m breakout_lab serve --port 8765`; öppna `http://127.0.0.1:8765/#metro` i webbläsaren (claude-in-chrome-skillen), byt strategi fram och tillbaka, kontrollera att siffror, lista och hash följer med och att Breakout-vyn ser ut som före. Ta skärmbild av båda.
- [ ] **Step 5:** Commit `feat: strategy switcher with per-strategy stats and candidate list`.

---

### Task 11: Frontend — graf, chips, Metro-plan och kontext

**Files:**
- Modify: `breakout_lab/static/app.js`, `breakout_lab/static/strategies.js`, `breakout_lab/static/style.css`, `breakout_lab/static/index.html`

**Interfaces:**
- Consumes: Metro-rad (`chart_levels`, `checks`, nivåer, `rr`, `regime`) och `strategies.metro.context`.
- Graf: `drawChart` ritar **endast** aktiv strategis nivåer. Breakout: motståndslinjen som i dag. Metro: varje `chart_levels`-post inom `[minPrice, maxPrice]` — `r1` heldragen `#ecc58a`, `r2/t1/t2` streckad accentfärg, `s1/s2` heldragen `#7d8da1`, `stop` heldragen `#f58a9e`; etikett till vänster. Legenden byts per strategi.
- Chips ovanför grafen: övriga strategiers status för vald aktie; klick → `setActive(id)`.
- Planpanel för Metro, fem rubriker i mallens ordning: **1. Makro & sentiment** (marknadsläge + noter; marknadsberättelse med datum och länk "Vecko_agent scout-rapport"; för kortlisteaktier rubriker med källa/datum/länk och reaktion per artikel ("Positivt mottagen +3,1 % mot index, 2,4× volym" / "Negativt mottagen …" / "Ingen tydlig reaktion" / "Reaktion okänd än") samt sammanfattning märkt "Marknadsreaktion, styr inte signalen"; annars "Inte i kortlistan"; för **alla** aktier knappen "Djupanalys i Vecko_agent" som i ny flik öppnar `https://github.com/DrinasKastrati/Vecko_agent/issues/new?title=` + `encodeURIComponent("analys: " + symbol)` + `&body=` + `encodeURIComponent("Begäran om aktieanalys för " + symbol + ". Skicka in ärendet så köas det automatiskt.")`, plus länken "Visa analyser" till `https://drinaskastrati.github.io/Vecko_agent/`), **2. Nivåer** (S2, S1, R1, R2, trend), **3. Scenarier** (bullish: trigger → T1/T2; bearish: under S1 − buffert → S2; sidledes: avvakta), **4. Risk/Reward** (entryreferens, stop, T1, R/R, antal aktier, planerad risk), **5. Slutsats** (status + orsaker + påminnelse om positionsstorlek i förhållande till total portföljrisk).
- All extern text via `el(tag, text)` / `textContent`. Länkar: `href` bara om URL börjar med `https://`; `rel="noopener noreferrer"`, `target="_blank"`.

- [ ] **Step 1:** Implementera.
- [ ] **Step 2:** `node --check` på båda filerna. Kör `grep -n "innerHTML\|insertAdjacentHTML\|outerHTML" breakout_lab/static/*.js` → inga träffar.
- [ ] **Step 3:** Kör hela Python-sviten.
- [ ] **Step 4:** Lokalt (demo, serve): välj en Metro-`buy`/`watch`-aktie; kontrollera att bara Metro-linjer syns, att byte till Breakout bara visar breakoutens motstånd, att chips byter strategi, och att panelen visar fem steg samt "Demodata har inga nyheter." Skärmbilder.
- [ ] **Step 5:** Commit `feat: Metro chart levels, cross-strategy chips and five-step plan`.

---

### Task 12: Frontend — backtest, inställningar, metodtext

**Files:**
- Modify: `breakout_lab/static/app.js`, `breakout_lab/static/index.html`, `breakout_lab/static/data-client.js`, `breakout_lab/static/strategies.js`

**Interfaces:**
- Consumes: `/api/backtest?strategy=metro` (Task 7).
- Backtest-sidan följer reglaget. Metro: rubrik "Tillför marknadsläget något?", tabell med varianterna "Metro" och "Metro utan regimfilter", notis **"Visning, inte bevis"** med texten ur `limitations`. Breakout oförändrat.
- Inställningar: gemensamma fält som i dag; Metro-specifika fält (alla `MetroConfig`-fält utom `shortlist_size`, `news_days`) visas när Metro är aktiv och skickas som `{"metro": {...hela blocket...}}`. I statiskt läge inaktiverade som i dag.
- Metodsidan: en sektion per strategi; Metro-sektionen sammanfattar §5 (nivåer, trend, trigger, mål, stop, R/R, marknadsläge, varför sentiment inte styr).

- [ ] **Step 1:** Implementera.
- [ ] **Step 2:** `node --check` på ändrade filer.
- [ ] **Step 3:** Kör hela Python-sviten.
- [ ] **Step 4:** Lokalt: kör Metro-backtestet, ändra `min_rr` till 3 och spara, kontrollera att `config.json` behåller övriga fält och att listan räknas om. Återställ `config.json` med `git checkout config.json` efteråt. Bygg statiskt: `build-site --source demo --output dist/site-check`, servera `dist/site-check` med `python -m http.server 8766 -d dist/site-check`, kontrollera reglage, graf och backtest i statiskt läge. Skärmbilder.
- [ ] **Step 5:** Commit `feat: per-strategy backtest, settings and method pages`.

---

### Task 13: Dokumentation och slutverifiering

**Files:**
- Create: `docs/strategy-metro.md` (regelspecifikation i samma stil som `docs/strategy.md`, med exakta förval)
- Modify: `README.md` (avsnitt om strategibyte, Metro, marknadsläge, nyhetsreaktion och Vecko_agent-knappen, overifierad nyhetstillgång i Basic), `docs/strategy.md` (en rad som hänvisar till `strategy-metro.md`)

- [ ] **Step 1:** Skriv dokumenten. Siffror och texter ska stämma med koden — kontrollera mot `MetroConfig` och orsakstexterna i `metro.py`.
- [ ] **Step 2:** Kör hela sviten: förväntat alla gröna utom de 2 kända Windows-felen; ange exakt utdata i överlämningen.
- [ ] **Step 3:** `PYTHONUTF8=1 python -m breakout_lab build-site --source demo --output dist/site-check` → exit 0; rapportera storlek på `dist/site-check`.
- [ ] **Step 4:** Ta bort `dist/site-check`. `git status` ska bara visa avsiktliga ändringar.
- [ ] **Step 5:** Commit `docs: describe Metro strategy and strategy switching`.
