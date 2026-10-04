from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from breakout_lab.models import Asset, Config
from breakout_lab.research import public_summary
from breakout_lab.selection_study import (variants, month_ends, momentum_signals,
    simulate_momentum, load_market_caps, filter_size, run_study)
from test_portfolio import bar


def candidate(symbol, day, score=1):
    return {"symbol": symbol, "date": day, "score": score}


class SelectionStudyTests(unittest.TestCase):
    def test_month_ends_exclude_final_partial_month(self):
        self.assertEqual(month_ends(['2024-01-30', '2024-01-31', '2024-02-01', '2024-02-02']),
                         ['2024-01-31'])

    def test_momentum_skips_latest_month_and_does_not_use_future_prices(self):
        first = date(2022, 1, 1)
        days = [(first+timedelta(days=i)).isoformat() for i in range(850)]
        spy = [bar(d) for d in days]
        months = month_ends(days)
        day = months[15]
        anchors = (months[14], months[8], months[2])
        prices = {anchors[0]: 20, anchors[1]: 10, anchors[2]: 5, day: 1000}
        stock = [bar(d, opening=prices.get(d, 10), high=prices.get(d, 10)+1,
                     low=prices.get(d, 10)-1, close=prices.get(d, 10)) for d in days]
        config = replace(Config(), min_dollar_volume=0)
        signals = momentum_signals([Asset('A', 'A')], {'A': stock, 'SPY': spy}, config, day, day)
        self.assertEqual(signals[day][0]['score'], 2)  # mean(20/10-1, 20/5-1)
        mutated = [b if b.date <= day else bar(b.date, opening=1, high=2, low=.5, close=1) for b in stock]
        self.assertEqual(signals, momentum_signals([Asset('A', 'A')],
                         {'A': mutated, 'SPY': spy}, config, day, day))
        # Removing the long-history anchor excludes the stock rather than
        # pretending its shorter history is twelve-month momentum.
        missing = [b for b in stock if b.date != anchors[2]]
        self.assertEqual(momentum_signals([Asset('A', 'A')], {'A': missing, 'SPY': spy}, config, day, day)[day], [])

    def test_monthly_next_open_cap_and_empty_selection_liquidation_with_fees(self):
        days = ['2024-01-31', '2024-02-01', '2024-02-02', '2024-02-05']
        names = [f'S{i:02}' for i in range(12)]
        histories = {s: [bar(d) for d in days] for s in names}
        signals = {days[0]: [candidate(s, days[0]) for s in names], days[2]: []}
        config = replace(Config(), account_equity=100_000)
        r = simulate_momentum(histories, signals, config, days[0], days[-1], days)
        self.assertEqual(r['equity_curve'][0]['positions'], 0)
        self.assertEqual(r['stats']['max_positions'], 10)
        self.assertEqual(r['stats']['closed_trades'], 10)
        self.assertEqual(r['stats']['open_positions'], 0)
        self.assertTrue(all(t['entry_date'] == days[1] and t['exit_date'] == days[3] for t in r['trades']))
        self.assertAlmostEqual(r['stats']['net_profit_usd'], sum(t['pnl_usd'] for t in r['trades']))
        self.assertLess(r['stats']['return'], 0)
        self.assertTrue(all(row['cash_usd'] >= 0 and row['positions'] <= 10 for row in r['equity_curve']))

    def test_retained_winner_is_not_resized_and_genuine_collapse_remains(self):
        days = ['2024-01-31', '2024-02-01', '2024-02-02', '2024-02-05']
        histories = {'A': [bar(days[0]), bar(days[1]),
            bar(days[2], opening=4, high=5, low=3, close=4),
            bar(days[3], opening=4, high=5, low=3, close=4)]}
        config = replace(Config(), account_equity=1000, slippage_bps=0, commission_per_share=0)
        r = simulate_momentum(histories, {days[0]: [candidate('A', days[0])],
            days[2]: [candidate('A', days[2])]}, config, days[0], days[-1], days)
        self.assertEqual(r['stats']['closed_trades'], 0)
        self.assertEqual(r['open_positions'][0]['shares'], 10)
        self.assertEqual(r['open_positions'][0]['entry_date'], days[1])
        self.assertAlmostEqual(r['stats']['return'], -.06)

    def test_missing_exit_bar_keeps_holding_and_prevents_eleventh_position(self):
        days = ['2024-01-31', '2024-02-01', '2024-02-02', '2024-02-05']
        names = [f'S{i:02}' for i in range(20)]
        histories = {s: [bar(d) for d in days if not(s == 'S00' and d == days[3])] for s in names}
        config = replace(Config(), account_equity=100_000, slippage_bps=0, commission_per_share=0)
        signals = {days[0]: [candidate(s, days[0]) for s in names[:10]],
                   days[2]: [candidate(s, days[2]) for s in names[10:]]}
        r = simulate_momentum(histories, signals, config, days[0], days[-1], days)
        self.assertEqual(r['stats']['max_positions'], 10)
        self.assertEqual(r['stats']['open_positions'], 10)
        self.assertIn('S00', [p['symbol'] for p in r['open_positions']])
        self.assertEqual(r['stats']['skipped']['position_limit'], 1)
        self.assertEqual(r['stats']['stale_position_sessions'], 1)

    def test_size_filters_block_missing_future_and_partial_data_and_use_strict_threshold(self):
        day = '2024-01-31'
        signals = {day: [candidate('A', day), candidate('B', day)]}
        complete = {('A', day): {'available_on': day, 'value': 1_000_000_000},
                    ('B', day): {'available_on': day, 'value': 2_000_000_000}}
        filtered, coverage = filter_size(signals, 1_000_000_000, complete)
        self.assertEqual([c['symbol'] for c in filtered[day]], ['B'])
        self.assertEqual(coverage['status'], 'complete')
        for records in (None, {('A', day): complete[('A', day)]},
                {**complete, ('B', day): {'available_on': '2024-02-01', 'value': 2_000_000_000}}):
            output, coverage = filter_size(signals, 1_000_000_000, records)
            self.assertIsNone(output)
            self.assertEqual(coverage['status'], 'blocked')
        self.assertIs(filter_size(signals, 0, None)[0], signals)

    def test_cap_loader_rejects_current_only_data_duplicate_vintages_and_nonfinite_values(self):
        data = {'schema': 1, 'currency': 'USD', 'point_in_time': True, 'source': 'test',
                'records': [{'symbol': 'A', 'date': '2024-01-31', 'available_on': '2024-01-31',
                             'market_cap_usd': 2_000_000_000}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'caps.json'
            path.write_text(json.dumps(data))
            records, meta = load_market_caps(path)
            self.assertEqual(records[('A', '2024-01-31')]['value'], 2_000_000_000)
            self.assertEqual(meta['records'], 1)
            for bad in ({**data, 'point_in_time': False}, {**data, 'currency': 'EUR'},
                        {**data, 'records': data['records']*2},
                        {**data, 'records': [{**data['records'][0], 'market_cap_usd': float('nan')}]}):
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    load_market_caps(path)

    def test_pipeline_six_statuses_complete_only_with_historical_coverage_and_encryption(self):
        from breakout_lab.selection_study import main
        from breakout_lab.pages import derive_key
        from base64 import b64decode
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        bars = [bar((date(2020, 9, 1)+timedelta(days=i)).isoformat()) for i in range(2200)]
        histories = {'A': bars, 'SPY': bars}
        assets = [Asset('A', 'A Common Stock')]
        metadata = {'as_of': bars[-1].date, 'adjustment': 'split,spin-off'}
        with tempfile.TemporaryDirectory() as directory:
            with patch('sys.argv', ['selection', '--output', directory]), \
                 patch('breakout_lab.selection_study.download_dataset', return_value=(assets, histories, metadata)), \
                 patch.dict('os.environ', {'DASHBOARD_PASSPHRASE': 'test-passphrase-12345', 'GITHUB_STEP_SUMMARY': ''}), \
                 patch('builtins.print'):
                self.assertEqual(main(), 0)
            public = json.loads((Path(directory)/'summary.json').read_text())
            self.assertEqual(len(public['planned_variants']), 6)
            self.assertEqual(len(public['variants']), 2)
            self.assertEqual(sum(c['status'] == 'blocked' for c in public['execution_matrix']), 4)
            self.assertNotIn('private_data_audit', public)
            self.assertIn('Blockerad', (Path(directory)/'report.md').read_text())
            envelope = json.loads((Path(directory)/'personal-report.encrypted.json').read_text())
            key = derive_key('test-passphrase-12345', b64decode(envelope['salt']))
            private = json.loads(AESGCM(key).decrypt(b64decode(envelope['nonce']),
                b64decode(envelope['ciphertext']), envelope['aad'].encode()))
            self.assertIn('momentum_signals', private['private_data_audit'])
            # Full six-run integration with explicit complete cap coverage.
            records = {('A', b.date): {'value': 6_000_000_000, 'available_on': b.date} for b in bars}
            with patch('builtins.print'):
                complete = run_study(assets, histories, metadata, Config(),
                    public['start'], public['end'], records, {'status': 'supplied'})
            self.assertEqual(len(complete['variants']), 6)
            self.assertTrue(all(c['status'] == 'completed' for c in complete['execution_matrix']))
            self.assertNotIn('private_data_audit', public_summary(complete))


if __name__ == '__main__':
    unittest.main()
