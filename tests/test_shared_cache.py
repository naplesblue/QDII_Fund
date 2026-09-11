import concurrent.futures
import datetime as dt
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from fund_atlas.shared_cache import SharedCache, CacheFailure, BACKOFF, quote_session, TZ

class CacheTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.clock=[dt.datetime(2026,9,11,10,tzinfo=TZ).timestamp()]
  self.cache=SharedCache(self.tmp.name,lambda:self.clock[0])
 def test_ttl_and_original_timestamp(self):
  loader=Mock(return_value={'nav':1.2});a,meta=self.cache.get('nav:1',loader)
  self.clock[0]+=21599;b,cached=self.cache.get('nav:1',loader)
  self.assertEqual(loader.call_count,1);self.assertEqual(cached['checked_at'],meta['checked_at']);self.assertTrue(cached['cached'])
  self.clock[0]+=1;self.cache.get('nav:1',loader);self.assertEqual(loader.call_count,2)
 def test_backoff_persists_and_discards_old_value(self):
  self.cache.get('nav:1',lambda:99);self.clock[0]+=21600
  loader=Mock(side_effect=ValueError('514'))
  for delay in BACKOFF:
   with self.assertRaises(CacheFailure) as error:self.cache.get('nav:1',loader)
   self.assertEqual(error.exception.meta['retry_at']-self.clock[0],delay)
   self.assertNotIn('value',self.cache.read('nav:1'))
   restarted=SharedCache(self.tmp.name,lambda:self.clock[0]);count=loader.call_count
   with self.assertRaises(CacheFailure):restarted.get('nav:1',loader)
   self.assertEqual(loader.call_count,count);self.clock[0]+=delay
  self.cache.get('nav:1',lambda:2);self.assertEqual(self.cache.read('nav:1')['failures'],0)
 def test_concurrent_cache_instances_share_one_loader(self):
  other=SharedCache(self.tmp.name,lambda:self.clock[0]);calls=[]
  def loader():calls.append(1);time.sleep(.03);return 'same'
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
   values=list(pool.map(lambda i:(self.cache if i%2 else other).get('history:1',loader)[0],range(8)))
  self.assertEqual(calls,[1]);self.assertEqual(values,['same']*8)
 def test_quotes_open_closed_holiday(self):
  loader=Mock(return_value={})
  self.cache.get('quotes',loader);self.clock[0]+=299;self.cache.get('quotes',loader);self.assertEqual(loader.call_count,1)
  self.clock[0]+=1;self.cache.get('quotes',loader);self.assertEqual(loader.call_count,2)
  self.clock[0]=dt.datetime(2026,9,11,15,1,tzinfo=TZ).timestamp();self.cache.get('quotes',loader)
  self.clock[0]=dt.datetime(2026,9,13,12,tzinfo=TZ).timestamp();self.cache.get('quotes',loader);self.assertEqual(loader.call_count,3)
  self.clock[0]=dt.datetime(2026,9,14,9,30,tzinfo=TZ).timestamp();self.cache.get('quotes',loader);self.assertEqual(loader.call_count,4)
  self.assertFalse(quote_session(dt.datetime(2026,10,1,10,tzinfo=TZ).timestamp())[1])
 def test_unknown_calendar_blocks_calls(self):
  self.clock[0]=dt.datetime(2027,1,4,10,tzinfo=TZ).timestamp();loader=Mock()
  with self.assertRaises(CacheFailure):self.cache.get('quotes',loader)
  loader.assert_not_called()

if __name__=='__main__':unittest.main()
