import unittest, datetime as dt, json, tempfile, pathlib
from unittest.mock import patch
from fund_atlas import server
from fund_atlas.server import performance, classify, parse_rows, TZ
class Metrics(unittest.TestCase):
 def series(self,event=''):
  dates=[dt.datetime(2023,9,8,tzinfo=TZ),dt.datetime(2024,9,8,tzinfo=TZ),dt.datetime(2025,9,8,tzinfo=TZ),dt.datetime(2026,9,8,tzinfo=TZ)]
  values=[1,1.2,.9,1.5];points=[dict(x=d.timestamp()*1000,y=v,unitMoney=event if i==2 else '',equityReturn=(v/values[i-1]-1)*100 if i else 0) for i,(d,v) in enumerate(zip(dates,values))]
  return 'var Data_netWorthTrend='+json.dumps(points)+';'
 def test_returns_and_drawdown(self):
  p=performance(self.series());self.assertAlmostEqual(p['returns']['3'],14.47,places=1);self.assertEqual(p['drawdowns']['3'],-25);self.assertNotIn('5',p['returns'])
 def test_dividend_rejected(self): self.assertNotIn('3',performance(self.series('分红'))['returns'])
 def test_nav_series_retains_dividend_even_when_return_rejected(self):
  result=performance(self.series('分红'))
  self.assertEqual(result['nav_series'][2],['2025-09-08',0.9,-25.0,'分红'])
  self.assertNotIn('3',result['returns'])
 def test_mismatch_rejected(self): self.assertNotIn('3',performance(self.series().replace('25.0','20.0'))['returns'])
 def test_quota(self):
  rows=[[str(i).zfill(6),'测试','QDII','1','09-09','暂停申购','开放','','10','100','1','1','0.1%'] for i in range(100)]
  self.assertIsNone(parse_rows(rows,'test')[0]['quota']); rows[0][5]='限大额';self.assertEqual(parse_rows(rows,'test')[0]['quota'],100)
 def test_classification(self):
  self.assertEqual(classify('纳斯达克100指数','',['1.600519'])[0],'a');self.assertEqual(classify('','',['105.AAPL'])[0],'pending');self.assertEqual(classify('纳斯达克100指数','',[])[0],'us')
class FieldUpdates(unittest.TestCase):
 def setUp(self):
  self.cache_tmp=tempfile.TemporaryDirectory();self.addCleanup(self.cache_tmp.cleanup)
  cache_patch=patch.object(server,'SOURCE_CACHE',server.SharedCache(self.cache_tmp.name));cache_patch.start();self.addCleanup(cache_patch.stop)
 def fund(self):
  return {'code':'008971','name':'测试','type':'QDII','currency':'RMB','listed':True,'category':'us','nav':99,'nav_date':'2020-01-01','returns':{'3':88},'drawdowns':{'3':-44},'premium':25,'fees':{'management':1.2,'custody':0.2},'quota':100,'purchase_status':'限大额','purchase_fee':'0.12%'}
 def test_nav_failure_clears_only_nav(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'data.json';path.write_text(json.dumps({'funds':[self.fund()]}))
   with patch.object(server,'DATA',path),patch.object(server,'latest_nav',side_effect=ValueError('offline')):
    result,status=server.retry('008971','nav')
   f=json.loads(path.read_text())['funds'][0]
   self.assertEqual(status,200);self.assertNotIn('nav',f);self.assertNotIn('nav_date',f)
   self.assertEqual(f['returns']['3'],88);self.assertEqual(f['fees']['management'],1.2);self.assertEqual(f['field_states']['nav']['status'],'error')
 def test_management_retry_shares_related_fees(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'data.json';path.write_text(json.dumps({'funds':[self.fund()]}))
   with patch.object(server,'DATA',path),patch.object(server,'detail',return_value={'fees':{'management':0.5,'custody':9,'service':0.1},'redemption':'1.5%'}) as call:
    result,status=server.retry('008971','management')
   f=result['fund'];self.assertEqual(f['fees'],{'management':0.5,'custody':9,'service':0.1});self.assertEqual(f['nav'],99);call.assert_called_once_with('008971')
 def test_history_retry_shares_returns_but_preserves_nav(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'data.json';path.write_text(json.dumps({'funds':[self.fund()]}))
   with patch.object(server,'DATA',path),patch.object(server,'history',return_value={'drawdowns':{'3':-20},'returns':{'3':12},'return_note':'test','periods':{'3':['2023-01-01','2026-01-01']},'nav_date':'2026-01-01'}):
    result,status=server.retry('008971','drawdowns')
   f=result['fund'];self.assertEqual(f['drawdowns']['3'],-20);self.assertEqual(f['returns']['3'],12);self.assertEqual(f['nav_date'],'2020-01-01')
 def test_full_refresh_no_stale_fallback_on_any_source_failure(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'data.json';path.write_text(json.dumps({'funds':[self.fund()]}))
   with patch.object(server,'DATA',path),patch.object(server,'fetch',side_effect=ValueError('offline')):
    server.refresh()
   f=json.loads(path.read_text())['funds'][0]
   for key in ['nav','nav_date','returns','drawdowns','quota','purchase_fee','premium']:self.assertNotIn(key,f)
   self.assertNotIn('management',f['fees']);self.assertEqual(f['field_states']['nav']['status'],'error');self.assertFalse(server.STATUS['running'])
 def test_independent_nav_survives_other_source_failures(self):
  with patch.object(server,'latest_nav',return_value={'nav':6.2,'nav_date':'2026-09-09','nav_at':'now'}),patch.object(server,'history',side_effect=ValueError('offline')),patch.object(server,'detail',side_effect=ValueError('offline')):
   f=server.enrich(self.fund())
  self.assertEqual(f['nav'],6.2);self.assertNotIn('returns',f);self.assertEqual(f['field_states']['nav']['status'],'ok')
 def test_retry_cache_reuses_source_and_retains_fetch_time(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'data.json';path.write_text(json.dumps({'funds':[self.fund()]}))
   with patch.object(server,'DATA',path),patch.object(server,'_fetch_latest_nav',return_value={'nav':6.2,'nav_date':'2026-09-09'}) as upstream:
    first,_=server.retry('008971','nav');second,_=server.retry('008971','nav')
   self.assertEqual(upstream.call_count,1);self.assertTrue(second['state']['cached']);self.assertEqual(first['state']['checked_at'],second['state']['checked_at'])
 def test_failure_cooldown_not_bypassed_by_retry(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'data.json';path.write_text(json.dumps({'funds':[self.fund()]}))
   with patch.object(server,'DATA',path),patch.object(server,'_fetch_latest_nav',side_effect=ValueError('514')) as upstream:
    first,_=server.retry('008971','nav');second,_=server.retry('008971','nav')
   self.assertEqual(upstream.call_count,1);self.assertNotIn('nav',second['fund']);self.assertEqual(first['state']['next_retry_at'],second['state']['next_retry_at'])
 def test_website_snapshot_seeds_nav_without_upstream(self):
  f=self.fund();f['field_states']={'nav':{'status':'ok','checked_at':server.now()}}
  server.seed_source_cache({'funds':[f]})
  with patch.object(server,'_fetch_latest_nav') as upstream:
   result=server.latest_nav('008971')
  upstream.assert_not_called();self.assertEqual(result['nav'],99);self.assertTrue(result['_cache']['cached'])
 def test_nav_history_reads_shared_series_without_fetch(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'data.json';path.write_text(json.dumps({'funds':[self.fund()]}))
   data=performance(Metrics().series('分红'))
   server.SOURCE_CACHE.write('history:008971',{'value':data,'checked_at':dt.datetime.now().timestamp()})
   with patch.object(server,'DATA',path),patch.object(server,'fetch') as upstream:
    result=server.nav_history('008971',3)
   upstream.assert_not_called();self.assertEqual(result['points'][-1][0],'2026-09-08')
   self.assertEqual(len(result['points']),4)
 def test_nav_history_does_not_serve_failed_old_value(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'data.json';path.write_text(json.dumps({'funds':[self.fund()]}))
   server.SOURCE_CACHE.write('history:008971',{'error':'offline','value':performance(Metrics().series())})
   with patch.object(server,'DATA',path):result=server.nav_history('008971',3)
   self.assertEqual(result['points'],[])
 def test_nav_history_uses_matching_legacy_evidence(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);data_path=root/'data.json';data_path.write_text(json.dumps({'funds':[self.fund()]}))
   evidence=root/'evidence';evidence.mkdir()
   raw='var fS_code="008971";'+Metrics().series('分红')
   (evidence/'008971-nav.js').write_text(raw)
   server.SOURCE_CACHE.write('history:008971',{'value':{'nav_date':'2026-09-08'},'checked_at':dt.datetime.now().timestamp()})
   with patch.object(server,'DATA',data_path),patch.object(server,'CACHE',evidence),patch.object(server,'fetch') as upstream:
    result=server.nav_history('008971',1)
   upstream.assert_not_called();self.assertEqual(result['points'][0][0],'2025-09-08')
   (evidence/'008971-nav.js').write_text(raw.replace('008971','999999'))
   with patch.object(server,'DATA',data_path),patch.object(server,'CACHE',evidence):
    missing=server.nav_history('008971',1)
   self.assertEqual(missing['points'],[])
 def test_legacy_failed_fields_removed(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'data.json';f=self.fund();f['error']='old failure';path.write_text(json.dumps({'funds':[f]}))
   with patch.object(server,'DATA',path):server.bootstrap()
   f=json.loads(path.read_text())['funds'][0]
   self.assertNotIn('nav',f);self.assertNotIn('error',f);self.assertEqual(f['quota'],100)
 def test_busy_retry_changes_nothing(self):
  server.LOCK.acquire()
  try:result,status=server.retry('008971','nav');self.assertEqual(status,202);self.assertTrue(result['joined'])
  finally:server.LOCK.release()
 def test_invalid_retry_rejected(self):
  self.assertEqual(server.retry('../x','nav')[1],400);self.assertEqual(server.retry('008971','nope')[1],400)
if __name__=='__main__': unittest.main()
