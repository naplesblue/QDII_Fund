#!/usr/bin/env python3
"""Read-only QDII public API probes. Python 3 + curl, no login required.
Run: python3 scripts/test_qdii_api.py
Raw responses: work/api-probe/ ; request results: work/research/api_probe_results.json
"""
import sys, concurrent.futures, datetime, json, pathlib, subprocess, urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent.parent
(ROOT/'work/research').mkdir(parents=True,exist_ok=True)
RAW=ROOT/'work/api-probe'; RAW.mkdir(parents=True,exist_ok=True)
def url(base,**params): return base+'?'+urllib.parse.urlencode(params)
PROBES={
 'purchase':url('https://fund.eastmoney.com/Data/Fund_JJJZ_Data.aspx',t=8,page='1,50000',js='reData',sort='fcode,asc'),
 'fund_names':'https://fund.eastmoney.com/js/fundcode_search.js',
 'etf_quotes':url('https://push2delay.eastmoney.com/api/qt/clist/get',pn=1,pz=100,po=1,np=1,ut='bd1d9ddb04089700cf9c27f6f7426281',fltt=2,invt=2,fid='f12',fs='b:MK0021,b:MK0022,b:MK0023,b:MK0024,b:MK0827',fields='f12,f14,f2,f402,f441,f297,f124'),
 'etf_quotes_ascending':url('https://push2delay.eastmoney.com/api/qt/clist/get',pn=1,pz=100,po=0,np=1,ut='bd1d9ddb04089700cf9c27f6f7426281',fltt=2,invt=2,fid='f12',fs='b:MK0021,b:MK0022,b:MK0023,b:MK0024,b:MK0827',fields='f12,f14,f2,f402,f441,f297,f124'),
 'etf_selected':url('https://push2delay.eastmoney.com/api/qt/ulist.np/get',secids='1.513500,0.159941,1.513100',fltt=2,invt=2,fields='f12,f14,f2,f402,f441,f297,f124'),
 'jisilu_unauth':url('https://www.jisilu.cn/data/qdii/qdii_list/E',rp=22),
 'fund_detail_161125':'https://fundf10.eastmoney.com/jbgk_161125.html',
 'fund_nav_161125':url('https://api.fund.eastmoney.com/f10/lsjz',fundCode='161125',pageIndex=1,pageSize=5),
 'fund_performance_161125':'https://fund.eastmoney.com/pingzhongdata/161125.js',
}
def probe(item):
 name,u=item; path=RAW/(name+'.txt')
 p=subprocess.run(['curl','-L','--max-time','22','--connect-timeout','8','-sS','-A','Mozilla/5.0','-H','Referer: https://fund.eastmoney.com/','-o',str(path),'-w','%{http_code}',u],capture_output=True,text=True)
 return dict(name=name,url=u,checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),http_status=p.stdout,exit_code=p.returncode,error=p.stderr.strip(),bytes=path.stat().st_size if path.exists() else 0,raw=str(path.relative_to(ROOT)))
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex: results=list(ex.map(probe,[(k,v) for k,v in PROBES.items() if not sys.argv[1:] or k in sys.argv[1:]]))
 previous=ROOT/'work/research/api_probe_results.json'
 if sys.argv[1:] and previous.exists():
  results=[r for r in json.loads(previous.read_text()) if r['name'] not in {x['name'] for x in results}]+results
 (ROOT/'work/research/api_probe_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 for r in results: print(r['name'],r['http_status'],r['exit_code'],r['bytes'],r['error'][:120])
