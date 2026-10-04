from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from breakout_lab.models import Asset, Bar, Config
from breakout_lab.portfolio import simulate_portfolio
from breakout_lab.research import (parse_directory, filter_universe, market_states,
    choose_signals, variants, period_windows, run_study, public_summary, save, walk_forward)
from test_portfolio import bar, signal


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.days = ["2024-01-01", "2024-01-02", "2024-01-03"]
        self.config = replace(Config(), account_equity=1000, risk_fraction=.02,
                              max_position_fraction=1, slippage_bps=0, commission_per_share=0)

    def sim(self,h,signals,**kwargs):
        return simulate_portfolio(h,signals,self.config,self.days[0],self.days[-1],self.days,**kwargs)

    def test_official_etf_and_positive_stock_name_are_both_required(self):
        content = "ACT Symbol|Security Name|ETF|Test Issue\nA|A Common Stock|N|N\nUCO|ProShares Ultra Bloomberg Crude Oil|Y|N\nW|W Warrant|N|N\nX|X Common Stock|N|Y\nD|D Depositary Shares|N|N\nFile Creation Time: 10042026||||\n"
        records = parse_directory(content,"ACT Symbol")
        assets=[Asset(s,s) for s in ("A","UCO","W","X","D","UNKNOWN")]
        selected,reasons=filter_universe(assets,records)
        self.assertEqual([a.symbol for a in selected],["A"])
        self.assertEqual(reasons['etf_test_or_unknown_flag'],2)
        self.assertEqual(reasons['missing_official_record'],1)
        self.assertEqual(selected[0].classification,"curated")
        self.assertFalse(filter_universe(assets,records,["A"])[0])
        with self.assertRaises(ValueError):
            parse_directory("Symbol|Security Name\nA|A Common Stock","Symbol")

    def test_failed_breakout_exits_next_open_and_open_gap_stop_has_priority(self):
        h={'A':[bar(self.days[0]),bar(self.days[1],high=10.3,low=9.8,close=10),
                bar(self.days[2],opening=9.7,high=10,low=9.5,close=9.8)]}
        r=self.sim(h,{self.days[0]:[signal('A')]},allocation='all_in',failure_exit=True)
        self.assertEqual(r['trades'][0]['exit_date'],self.days[2])
        self.assertEqual(r['trades'][0]['exit_reason'],'failed_breakout_next_open')
        self.assertEqual(r['trades'][0]['exit'],9.7)
        h['A'][-1]=bar(self.days[2],opening=8.5,high=9,low=8,close=8.7)
        r=self.sim(h,{self.days[0]:[signal('A')]},allocation='all_in',failure_exit=True)
        self.assertEqual(r['trades'][0]['exit_reason'],'stop_gap')

    def test_portfolio_heat_and_position_limits_bind_at_entry(self):
        h={s:[bar(d) for d in self.days] for s in ('A','B','C')}
        sig={self.days[0]:[signal(s) for s in h]}
        r=self.sim(h,sig,max_portfolio_risk=.03)
        self.assertEqual([p['shares'] for p in r['open_positions']],[20,10])
        self.assertAlmostEqual(sum(p['shares']*(p['entry']-p['stop']) for p in r['open_positions']),30)
        r=self.sim(h,sig,max_positions_limit=1)
        self.assertEqual(r['stats']['open_positions'],1)
        self.assertEqual(r['stats']['skipped']['position_limit'],2)
        r=self.sim(h,sig,max_exposure=.25)
        self.assertEqual(sum(p['shares'] for p in r['open_positions']),25)

    def test_atr_stop_only_tightens_and_target_can_be_disabled(self):
        h={'A':[bar(self.days[0]),bar(self.days[1],high=13,low=9.8,close=12),bar(self.days[2],opening=12,high=14,low=11,close=13)]}
        sig={self.days[0]:[signal('A',stop=5)]}
        r=self.sim(h,sig,allocation='all_in',entry_stop_atr=2,use_target=False)
        self.assertEqual(r['open_positions'][0]['stop'],6)
        self.assertIsNone(r['open_positions'][0]['target'])
        sig={self.days[0]:[signal('A',stop=9)]}
        r=self.sim(h,sig,allocation='all_in',entry_stop_atr=2,use_target=False)
        self.assertEqual(r['open_positions'][0]['stop'],9)

    def test_channel_exit_uses_previous_lows_and_sells_next_open(self):
        early=[bar((date(2023,12,20)+timedelta(days=i)).isoformat()) for i in range(12)]
        h={'A':early+[bar(self.days[0]),bar(self.days[1],high=10,low=9.1,close=9.2),
                         bar(self.days[2],opening=9.3,high=10,low=9.2,close=9.5)]}
        r=self.sim(h,{self.days[0]:[signal('A',stop=8)]},allocation='all_in',exit_rule='channel10',use_target=False)
        self.assertEqual(r['trades'][0]['exit_date'],self.days[2])
        self.assertEqual(r['trades'][0]['exit_reason'],'channel10_next_open')
        self.assertEqual(r['trades'][0]['exit'],9.3)

    def test_market_exit_does_not_sell_at_same_close(self):
        h={'A':[bar(self.days[0]),bar(self.days[1],high=10.3,low=9.8,close=10.2),
                bar(self.days[2],opening=10.1,high=10.3,low=9.9,close=10.2)]}
        r=self.sim(h,{self.days[0]:[signal('A')]},allocation='all_in',market_exit_dates={self.days[1]:True})
        self.assertEqual(r['trades'][0]['exit_date'],self.days[2])
        self.assertEqual(r['trades'][0]['exit'],10.1)
        self.assertEqual(r['trades'][0]['exit_reason'],'market_next_open')

    def test_exit_event_cache_and_future_bars_cannot_change_prior_exits(self):
        h={'A':[bar(self.days[0]),bar(self.days[1],high=11.5,low=9.5,close=11.5),
                bar(self.days[2],opening=11,high=11.5,low=10,close=11)]}
        sig={self.days[0]:[signal('A')]}; cache={}
        with patch('breakout_lab.portfolio.calculate',return_value={'atr':[.5,.5,.5]}):
            a=self.sim(h,sig,allocation='all_in',exit_rule='atr_trailing',exit_event_cache=cache)
        with patch('breakout_lab.portfolio.calculate',side_effect=AssertionError('cache not reused')):
            b=self.sim(h,sig,allocation='all_in',exit_rule='atr_trailing',exit_event_cache=cache,
                       bar_index={'A':{b.date:b for b in h['A']}})
        self.assertEqual(a,b)
        h['A'] += [bar('2024-01-04',opening=11,high=100,low=10,close=99)]
        with patch('breakout_lab.portfolio.calculate',return_value={'atr':[.5,.5,.5,9]}):
            c=self.sim(h,sig,allocation='all_in',exit_rule='atr_trailing')
        self.assertEqual(a,c)

    def test_market_filter_is_causal_and_requires_rising_sma(self):
        bars=[bar((date(2023,1,1)+timedelta(days=i)).isoformat(),opening=10+i*.01,high=11+i*.01,low=9+i*.01,close=10+i*.01) for i in range(250)]
        states=market_states(bars)
        self.assertFalse(states[bars[218].date])
        self.assertTrue(states[bars[-1].date])
        self.assertEqual(states, {k:v for k,v in market_states(bars+[bar('2024-01-01',close=1,opening=1,high=2,low=.5)]).items() if k in states})

    def test_signal_filters_and_rs_ranking_do_not_mutate_shared_signals(self):
        c={**signal('A'), 'golden_windows':[20], 'market_ok':True, 'rs63':.1,
           'dollar_volume':60_000_000,'atr_fraction':.04,'stop_fraction':.1}
        groups={'baseline':{self.days[0]:[c]}}
        v={'family':'baseline','golden':20,'market':True,'rs':True,'quality':True,'rank':'rs'}
        got=choose_signals(groups,v)
        self.assertEqual(got[self.days[0]][0]['score'],.1)
        self.assertEqual(c['score'],100)
        self.assertFalse(choose_signals(groups,{**v,'golden':10}))

    def test_year_windows_are_nonoverlapping_and_walk_forward_never_uses_next_year_to_select(self):
        windows=period_windows('2021-10-02','2026-10-02')
        self.assertEqual(windows['year1'],('2021-10-02','2022-10-01'))
        self.assertEqual(windows['year5'],('2025-10-02','2026-10-02'))
        rows=[]
        for identifier,score,future in [('A',.2,-.5),('B',.1,1.0)]:
            periods={f'train{i}':{'stats':{'closed_trades':30,'return':score,'cagr':score,'max_drawdown':.1}} for i in (2,3,4)}
            periods.update({f'year{i}':{'stats':{'return':future,'max_drawdown':abs(future)}} for i in (3,4,5)})
            rows.append({'variant':{'id':identifier},'periods':periods})
        self.assertTrue(all(f['selected']=='A' for f in walk_forward(rows)['folds']))

    def test_small_study_encrypted_roundtrip_no_public_fills_or_synthetic_step_summary(self):
        bars=[]
        for i in range(2200):
            p=100+i*.01
            bars.append(Bar((date(2020,9,1)+timedelta(days=i)).isoformat(),p,p+.1,p-.1,p,1_000_000))
        end=bars[-1].date
        h={'A':bars,'SPY':bars};v=[variants()[0]]
        with patch('builtins.print'):
            r=run_study([Asset('A','A Common Stock')],h,{'as_of':end},Config(),'2021-09-08',end,v)
        public=public_summary(r)
        for p in public['variants'][0]['periods'].values():
            self.assertNotIn('trades',p)
            self.assertNotIn('open_positions',p)
        with tempfile.TemporaryDirectory() as directory:
            with patch('builtins.print'),patch.dict('os.environ',{'GITHUB_STEP_SUMMARY':''}):
                save(r,directory,'test-passphrase-12345')
            self.assertEqual(json.loads((Path(directory)/'summary.json').read_text()),json.loads(json.dumps(public)))
            from base64 import b64decode
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from breakout_lab.pages import derive_key
            e=json.loads((Path(directory)/'personal-report.encrypted.json').read_text())
            key=derive_key('test-passphrase-12345',b64decode(e['salt']))
            private=json.loads(AESGCM(key).decrypt(b64decode(e['nonce']),b64decode(e['ciphertext']),e['aad'].encode()))
            self.assertEqual(private,json.loads(json.dumps(r)))
        self.assertEqual(len(variants()),36)
        self.assertEqual(len({v['id'] for v in variants()}),36)


if __name__=='__main__':
    unittest.main()
