import datetime as dt
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from fund_atlas.premium_history import PremiumHistory
from fund_atlas.shared_cache import TZ, SharedCache
from fund_atlas import server


class PremiumSamples(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / 'history.sqlite3'
        self.history = PremiumHistory(self.path)
        self.now = dt.datetime(2026, 9, 23, 10, tzinfo=TZ).timestamp()
        self.fund = dict(code='513100', price=2.2, iopv=2, quote_timestamp=self.now,
                         quote_date='20260923')

    def test_persistence_dedup_and_window(self):
        self.assertEqual(self.history.append([self.fund], self.now), 1)
        self.assertEqual(self.history.append([self.fund], self.now + 300), 0)
        records = PremiumHistory(self.path).read('513100', 7, self.now + 300)
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0]['premium'], 10)
        self.assertEqual(self.history.read('513100', 7, self.now + 8 * 86400), [])
        self.assertEqual(self.history.read('513390', 7, self.now), [])

    def test_invalid_stale_and_off_session_quotes_rejected(self):
        for update in [dict(iopv=0), dict(price=float('nan')), dict(quote_date='20260922'),
                       dict(quote_timestamp=self.now-1800), dict(quote_timestamp=self.now+60),
                       dict(quote_timestamp='bad')]:
            self.assertEqual(self.history.append([self.fund | update], self.now), 0)
        weekend = dt.datetime(2026, 9, 26, 10, tzinfo=TZ).timestamp()
        self.assertEqual(self.history.append([self.fund | dict(quote_timestamp=weekend,quote_date='20260926')],weekend),0)

    def test_shared_manual_and_scheduled_collection(self):
        cache = SharedCache(pathlib.Path(self.tmp.name)/'cache', lambda:self.now)
        data = {'funds':[dict(code='513100',listed=True)]}
        row = dict(f12='513100', f2=2.2, f441=2, f124=self.now, f297=20260923)
        with patch.object(server,'SOURCE_CACHE',cache), patch.object(server,'PREMIUM_HISTORY',self.history), \
             patch.object(server,'_fetch_all_quotes',return_value={'513100':row}) as fetch, \
             patch.object(server,'load',return_value=data), patch.object(server,'atomic'), \
             patch.object(server.time,'time',return_value=self.now):
            self.assertTrue(server.collect_premiums())
            server.quotes(data['funds'])
            self.assertFalse(server.collect_premiums())
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(len(self.history.read('513100',7,self.now)),1)
            server.LOCK.acquire()
            try:self.assertFalse(server.collect_premiums())
            finally:server.LOCK.release()
            # Source failure later clears current values, but cannot erase historic samples.
            cache.clock=lambda:self.now+400
            with patch.object(server,'_fetch_all_quotes',side_effect=ValueError('offline')):
                server.quotes(data['funds'])
            self.assertNotIn('premium',data['funds'][0])
            self.assertEqual(len(self.history.read('513100',7,self.now)),1)

    def test_closed_market_does_not_request_upstream(self):
        with patch.object(server,'quote_session',return_value=('2026-09-23',False)), \
             patch.object(server,'_fetch_all_quotes') as fetch:
            self.assertFalse(server.collect_premiums())
            fetch.assert_not_called()
