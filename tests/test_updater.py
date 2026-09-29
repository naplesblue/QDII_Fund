import threading
import unittest
from unittest.mock import Mock, patch
from fund_atlas import server

class UpdaterTests(unittest.TestCase):
 def run_round(self, result=True, error=None):
  stop=threading.Event()
  stop.wait=Mock(side_effect=lambda delay: stop.set())
  with patch.dict(server.UPDATER), patch.object(server,'refresh',side_effect=error,return_value=result) as refresh:
   server.data_updater(stop)
   refresh.assert_called_once_with()
   return stop.wait.call_args.args[0],server.UPDATER.copy()
 def test_success_waits_after_completion(self):
  delay,state=self.run_round()
  self.assertEqual(delay,1800)
  self.assertIsNotNone(state['last_completed'])
  self.assertIsNotNone(state['next_check'])
 def test_busy_retries_without_overlapping(self):
  delay,_=self.run_round(False)
  self.assertEqual(delay,30)
 def test_exception_does_not_kill_scheduler(self):
  delay,state=self.run_round(error=ValueError('test failure'))
  self.assertEqual(delay,300)
  self.assertEqual(state['error'],'test failure')
 def test_legacy_refresh_does_not_start_upstream(self):
  handler=object.__new__(server.Handler)
  handler.path='/api/refresh';handler.headers={};handler.send_json=Mock()
  with patch.object(server,'refresh') as refresh,patch.object(server.threading,'Thread') as thread:
   handler.do_POST()
   refresh.assert_not_called();thread.assert_not_called()
   self.assertTrue(handler.send_json.call_args.args[0]['snapshot_only'])

 def test_snapshot_compression_preserves_payload(self):
  import gzip, io, json
  payload={'funds':['test fund']*1000}
  for accept in ('gzip, deflate, br','gzip;q=0',''):
   handler=object.__new__(server.Handler)
   handler.headers={'Accept-Encoding':accept};handler.wfile=io.BytesIO()
   handler.send_response=Mock();handler.send_header=Mock();handler.end_headers=Mock()
   handler.send_json(payload)
   headers=dict(call.args for call in handler.send_header.call_args_list)
   body=handler.wfile.getvalue()
   self.assertEqual(int(headers['Content-Length']),len(body))
   if accept.startswith('gzip,'):
    self.assertEqual(headers['Content-Encoding'],'gzip')
    self.assertLess(len(body),1000);body=gzip.decompress(body)
   else:self.assertNotIn('Content-Encoding',headers)
   self.assertEqual(json.loads(body),payload)
