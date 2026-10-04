from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import json
import tempfile
from unittest.mock import patch
import unittest

from breakout_lab.concentrated import (variants, apply_identity_starts,
    audit_moves, validate_caps, drawdown_details)
from breakout_lab.models import Config
from breakout_lab.portfolio import simulate_portfolio
from breakout_lab.providers import Alpaca
from breakout_lab.research import public_summary
from test_portfolio import bar, signal


class ConcentratedTests(unittest.TestCase):
    def test_caps_bind_with_spare_cash_and_rejected_signals_never_exceed_them(self):
        days = ['2024-01-01', '2024-01-02', '2024-01-03']
        config = replace(Config(), account_equity=100_000, risk_fraction=.001,
                         slippage_bps=0, commission_per_share=0)
        names = [f'S{i:02}' for i in range(14)]
        histories = {s: [bar(day) for day in days] for s in names}
        signals = {days[0]: [signal(s) for s in reversed(names)],
                   days[1]: [signal(s, days[1]) for s in names]}
        for cap in (5, 6, 10):
            with self.subTest(cap=cap):
                result = simulate_portfolio(histories, signals, config, days[0], days[-1],
                                            days, max_positions_limit=cap)
                self.assertEqual(result['stats']['max_positions'], cap)
                self.assertGreater(result['stats']['cash_usd'], 0)
                self.assertEqual([p['symbol'] for p in result['open_positions']], names[:cap])
                self.assertTrue(all(row['positions'] <= cap for row in result['equity_curve']))
                self.assertGreaterEqual(result['stats']['skipped']['position_limit'], 14-cap)
                wrapped = {'variants': [{'variant': {'max_positions_limit': cap},
                                         'periods': {'full': result}, 'stress': result}]}
                validate_caps(wrapped)
                result['stats']['max_positions'] = cap + 1
                with self.assertRaises(AssertionError):
                    validate_caps(wrapped)

    def test_old_biohaven_history_is_not_used_for_new_security_warmup(self):
        histories = {'BHVN': [bar('2022-10-03'), bar('2022-10-04'), bar('2022-10-05')],
                     'OTHER': [bar('2022-10-03')]}
        clean, removed = apply_identity_starts(histories)
        self.assertEqual([b.date for b in clean['BHVN']], ['2022-10-04', '2022-10-05'])
        self.assertEqual(removed['BHVN'], 1)
        self.assertEqual(len(histories['BHVN']), 3)
        self.assertEqual(clean['OTHER'], histories['OTHER'])

    def test_large_genuine_price_collapse_is_flagged_but_never_removed(self):
        histories = {'A': [bar('2024-01-01'),
                           bar('2024-01-02', opening=4, high=4.5, low=3.5, close=4)]}
        clean, _ = apply_identity_starts(histories)
        events = audit_moves(clean)
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]['overnight_return'], -.6)
        self.assertEqual(clean['A'], histories['A'])

    def test_spin_off_adjustment_is_sent_on_every_page_and_bad_mode_fails_before_network(self):
        with patch.dict('os.environ', {'ALPACA_API_KEY': 'test', 'ALPACA_API_SECRET': 'test'}):
            provider = Alpaca()
        calls = []
        pages = [{'bars': {}, 'next_page_token': 'second'}, {'bars': {}}]
        def get(host, route, params):
            calls.append(params.copy())
            return pages.pop(0)
        provider.get = get
        provider.bars(['A'], '2024-01-01', '2024-01-02', adjustment='split,spin-off')
        self.assertEqual([c['adjustment'] for c in calls], ['split,spin-off', 'split,spin-off'])
        self.assertEqual(calls[1]['page_token'], 'second')
        with self.assertRaises(ValueError):
            provider.bars(['A'], '2024-01-01', '2024-01-02', adjustment='unsupported')
        self.assertEqual(len(calls), 2)

    def test_private_price_audit_cannot_leak_into_public_summary(self):
        result = {'metadata': {'adjustment': 'split,spin-off'}, 'variants': [],
                  'private_data_audit': {'secret_prices': [148.5, 10.5]}}
        self.assertNotIn('private_data_audit', public_summary(result))
        self.assertIn('private_data_audit', result)

    def test_drawdown_dates_and_daily_return_use_previous_account_value(self):
        result = {'start': '2024-01-01', 'stats': {'initial_usd': 100},
                  'equity_curve': [{'date': '2024-01-01', 'equity_usd': 120},
                                   {'date': '2024-01-02', 'equity_usd': 60},
                                   {'date': '2024-01-03', 'equity_usd': 90}]}
        details = drawdown_details(result)
        self.assertEqual(details['decline']['peak_date'], '2024-01-01')
        self.assertEqual(details['decline']['trough_date'], '2024-01-02')
        self.assertEqual(details['decline']['drawdown'], .5)
        self.assertEqual(details['worst_day'], {'date': '2024-01-02', 'return': -.5})

    def test_new_manifest_is_bounded_and_old_research_manifest_is_preserved(self):
        from breakout_lab.research import variants as original_variants
        self.assertEqual(len(original_variants()), 36)
        self.assertEqual(len(variants()), 18)
        self.assertEqual(len({v['id'] for v in variants()}), 18)
        self.assertEqual({v['max_positions_limit'] for v in variants()}, {5, 6, 10})

    def test_complete_pipeline_saves_all_variants_and_encrypts_price_audit(self):
        from breakout_lab.concentrated import main
        from breakout_lab.models import Asset
        from breakout_lab.pages import derive_key
        from base64 import b64decode
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        bars = [bar((date(2020,9,1) + timedelta(days=i)).isoformat()) for i in range(2200)]
        histories = {'A': bars, 'SPY': bars}
        metadata = {'as_of': bars[-1].date, 'adjustment': 'split,spin-off'}
        with tempfile.TemporaryDirectory() as directory:
            with patch('sys.argv', ['concentrated', '--output', directory]), \
                 patch('breakout_lab.concentrated.download_dataset', return_value=([Asset('A', 'A Common Stock')], histories, metadata)), \
                 patch('breakout_lab.providers.Alpaca.bars', return_value={'BHVN': bars}), \
                 patch.dict('os.environ', {'ALPACA_API_KEY': 'test', 'ALPACA_API_SECRET': 'test',
                                          'DASHBOARD_PASSPHRASE': 'test-passphrase-12345', 'GITHUB_STEP_SUMMARY': ''}), \
                 patch('builtins.print'):
                self.assertEqual(main(), 0)
            public = json.loads((Path(directory) / 'summary.json').read_text())
            self.assertEqual(len(public['variants']), 18)
            self.assertNotIn('private_data_audit', public)
            self.assertIn('Högst innehav', (Path(directory) / 'report.md').read_text())
            envelope = json.loads((Path(directory) / 'personal-report.encrypted.json').read_text())
            key = derive_key('test-passphrase-12345', b64decode(envelope['salt']))
            private = json.loads(AESGCM(key).decrypt(b64decode(envelope['nonce']),
                b64decode(envelope['ciphertext']), envelope['aad'].encode()))
            self.assertIn('private_data_audit', private)
            self.assertEqual(len(private['private_data_audit']['split_only']['BHVN']), 2200)


if __name__ == '__main__':
    unittest.main()
