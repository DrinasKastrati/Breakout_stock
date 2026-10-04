from dataclasses import replace
from datetime import date, timedelta
import unittest

from breakout_lab.backtest import backtest, simulate_trade, summary
from breakout_lab.engine import evaluate, position_plan, scan
from breakout_lab.indicators import calculate, ema, sma
from breakout_lab.models import Asset, Bar, Config


def history():
    bars = []
    for i in range(300):
        p = 50+i*.1 if i < 270 else 77+(i-270)*.025
        bars.append(Bar((date(2024,1,1)+timedelta(days=i)).isoformat(),p,p+.35,p-.35,p,2_000_000))
    resistance = max(b.high for b in bars[-21:-1])
    p = resistance+.3
    bars[-1] = Bar(bars[-1].date, resistance-.1,p+.2,resistance-.3,p,5_000_000)
    return bars


class Indicators(unittest.TestCase):
    def test_ema_sma_seed_and_warmup(self):
        self.assertEqual(ema([1,2,3,4],3),[None,None,2,3])
        self.assertEqual(sma([1,2,3,4],3),[None,None,2,3])

    def test_causal_series(self):
        bars=history()
        past=calculate(bars[:200])
        extended=calculate(bars)
        for key in past:
            self.assertEqual(past[key],extended[key][:200])

    def test_atr_accounts_for_gap(self):
        bars=[Bar(f"2024-01-{i+1:02}",100,101,99,100,1000) for i in range(13)]
        bars.append(Bar("2024-01-14",110,111,109,110,1000))
        self.assertAlmostEqual(calculate(bars)["atr"][-1],(13*2+11)/14)

    def test_short_history_has_aligned_series(self):
        for length in (0,1,13,25,26,33,34):
            result=calculate(history()[:length])
            self.assertTrue(all(len(v)==length for v in result.values()))


class Strategy(unittest.TestCase):
    def setUp(self):
        self.bars=history()
        self.asset=Asset("TEST","Test company")
        self.config=replace(Config(),require_macd=False)

    def test_resistance_excludes_signal_candle(self):
        result=evaluate(self.asset,self.bars,self.config)
        expected=max(b.high for b in self.bars[-21:-1])
        self.assertEqual(result["resistance"],expected)
        self.assertGreater(self.bars[-1].high,expected)
        self.assertEqual(result["status"],"breakout")
        self.assertEqual(result["relative_volume"],2.5)

    def test_future_bars_cannot_change_signal(self):
        result=evaluate(self.asset,self.bars,self.config,index=299)
        future=self.bars+[Bar("2025-01-01",1000,1100,900,1000,900_000_000)]
        self.assertEqual(result,evaluate(self.asset,future,self.config,index=299,indicators=calculate(future)))

    def test_extension_rejects_chasing(self):
        last=self.bars[-1]
        self.bars[-1]=Bar(last.date,last.open,120,last.low,110,last.volume)
        self.assertEqual(evaluate(self.asset,self.bars,self.config)["status"],"extended")

    def test_missing_fundamentals_fail_active_filter(self):
        result=evaluate(self.asset,self.bars,replace(self.config,min_market_cap=500_000_000))
        self.assertEqual(result["status"],"excluded")

    def test_stale_quotes_are_excluded(self):
        rows=scan([self.asset],{"TEST":self.bars},self.config,as_of="2025-01-01")
        self.assertEqual(rows[0]["status"],"excluded")

    def test_position_cap_and_risk_budget(self):
        plan=position_plan(100,99,Config())
        self.assertEqual(plan["shares"],150)
        self.assertLessEqual(plan["risk_usd"],500)
        self.assertEqual(position_plan(100,100,Config())["shares"],0)

    def test_backtest_rejects_current_metadata_filters(self):
        with self.assertRaises(ValueError):
            backtest([self.asset],{"TEST":self.bars},replace(self.config,earnings_blackout_days=3))
        with self.assertRaises(ValueError):
            backtest([self.asset],{"TEST":self.bars},replace(self.config,min_market_cap=1))


class Execution(unittest.TestCase):
    def setUp(self):
        self.config=replace(Config(),slippage_bps=0,commission_per_share=0,max_holding_bars=2)
        self.candidate={"stop":97,"resistance":100,"atr":3}
        self.signal=Bar("2024-01-01",100,102,99,101,1000)

    def test_entry_is_next_open(self):
        bars=[self.signal,Bar("2024-01-02",102,103,100,102,1000),Bar("2024-01-03",102,103,101,102,1000)]
        trade=simulate_trade(bars,0,self.candidate,self.config)
        self.assertEqual(trade["entry_date"],"2024-01-02")
        self.assertEqual(trade["entry"],102)

    def test_stop_wins_ambiguous_candle(self):
        trade=simulate_trade([self.signal,Bar("2024-01-02",101,120,90,101,1000)],0,self.candidate,self.config)
        self.assertEqual(trade["exit_reason"],"stop")
        self.assertEqual(trade["r_multiple"],-1)

    def test_stop_gap_fills_open(self):
        bars=[self.signal,Bar("2024-01-02",101,102,100,101,1000),Bar("2024-01-03",90,92,88,90,1000)]
        trade=simulate_trade(bars,0,self.candidate,self.config)
        self.assertEqual(trade["exit"],90)
        self.assertLess(trade["r_multiple"],-1)

    def test_gap_too_far_above_breakout_skips_entry(self):
        bars=[self.signal,Bar("2024-01-02",120,121,119,120,1000)]
        self.assertIsNone(simulate_trade(bars,0,self.candidate,self.config))

    def test_unfinished_trade_not_forced_closed(self):
        bars=[self.signal,Bar("2024-01-02",101,102,100,101,1000)]
        self.assertTrue(simulate_trade(bars,0,self.candidate,self.config)["open"])

    def test_costs_reduce_result(self):
        bars=[self.signal,Bar("2024-01-02",101,102,100,101,1000),Bar("2024-01-03",101,102,100,101,1000)]
        trade=simulate_trade(bars,0,self.candidate,replace(self.config,slippage_bps=10,commission_per_share=.005))
        self.assertLess(trade["pnl_usd"],0)

    def test_no_trades_has_no_fake_win_rate(self):
        self.assertIsNone(summary([])["win_rate"])
        self.assertIsNone(summary([])["expectancy_r"])


class Validation(unittest.TestCase):
    def test_bad_config(self):
        for overrides in ({"risk_fraction":.5},{"require_macd":"false"},{"min_price":float("nan")},{"lookback":2.5},{"oops":1},{"allowed_sectors":"Tech"}):
            with self.assertRaises(ValueError):
                Config.from_dict(overrides)

    def test_invalid_ohlc(self):
        with self.assertRaises(ValueError):
            Bar("2024-01-01",100,90,80,100,100)
        with self.assertRaises(ValueError):
            Bar("2024-01-01",100,110,90,100,float("nan"))


if __name__=="__main__":
    unittest.main()
