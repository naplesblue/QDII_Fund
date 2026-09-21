#!/usr/bin/env python3
"""Local read-only fund screener. Run python3 -m fund_atlas; refresh via UI or --refresh."""
import concurrent.futures, csv, io, os, datetime as dt, html, json, math, pathlib, re, subprocess, threading, time, urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from .channels import classify_channel, LABELS as CHANNEL_LABELS
from .shared_cache import SharedCache, CacheFailure, TTLS, quote_session
ROOT=pathlib.Path(__file__).resolve().parent.parent
RUNTIME=pathlib.Path(os.environ.get('FUND_DATA_DIR',str(ROOT/'work/runtime')))
RUNTIME.mkdir(parents=True,exist_ok=True)
CACHE=RUNTIME/'evidence'; CACHE.mkdir(parents=True,exist_ok=True)
DATA=RUNTIME/'data.json'
SOURCE_CACHE=SharedCache(RUNTIME/'cache')
ALLOWED_ORIGINS=set(os.environ.get('FUND_ALLOWED_ORIGINS','http://127.0.0.1:8765,http://localhost:8765').split(','))
LOCK=threading.Lock()
STATUS={'running':False,'done':0,'total':0,'errors':0,'message':'尚未刷新'}
TZ=dt.timezone(dt.timedelta(hours=8))
def now(): return dt.datetime.now(TZ).isoformat(timespec='seconds')
def fetch(url):
 time.sleep(0.2)
 p=subprocess.run(['curl','--fail','-L','--max-time','18','--connect-timeout','6','-sS','-A','Mozilla/5.0','-H','Referer: https://fund.eastmoney.com/',url],capture_output=True)
 if p.returncode:
  status=re.search(r'error: (\d{3})',p.stderr.decode(errors='replace'))
  raise ValueError('上游返回错误（HTTP '+status[1]+'）' if status else '上游网络请求失败')
 s=p.stdout.decode('utf-8-sig')
 if not s.strip(): raise ValueError('上游返回空数据')
 return s

def variable(s,name):
 m=re.search(r'var\s+'+re.escape(name)+r'\s*=\s*',s)
 return json.JSONDecoder().raw_decode(s[m.end():])[0] if m else None

def clean(s): return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>','',s))).strip()
def cell(s,key):
 m=re.search(r'<th[^>]*>\s*'+re.escape(key)+r'\s*</th>\s*<td[^>]*>(.*?)</td>',s,re.S)
 return clean(m[1]) if m else ''
def section(s,key):
 m=re.search(r'<label[^>]*>'+key+r'</label>.*?<p>(.*?)</p>',s,re.S)
 return clean(m[1]) if m else ''
def number(s):
 try:
  n=float(s); return n if math.isfinite(n) else None
 except (ValueError,TypeError): return None

def performance(s):
 points=variable(s,'Data_netWorthTrend') or []
 points=[p for p in points if isinstance(p,dict) and number(p.get('x')) is not None and number(p.get('y')) is not None and p['y']>0]
 points.sort(key=lambda p:p['x'])
 if not points: return {'return_note':'暂无有效净值序列'}
 end=dt.datetime.fromtimestamp(points[-1]['x']/1000,TZ)
 out={'nav_date':end.date().isoformat(),'nav':points[-1]['y'],'returns':{},'drawdowns':{},'periods':{},'return_note':'净值法估算；仅展示窗口内无分红拆分且涨跌幅校验通过的数据。净值已计提持续费用。'}
 for years in [1,3,5]:
  try: target=end.replace(year=end.year-years)
  except ValueError: target=end.replace(year=end.year-years,day=28)
  before=[i for i,p in enumerate(points) if p['x']<=target.timestamp()*1000]
  if not before: continue
  ix=before[-1]; start=dt.datetime.fromtimestamp(points[ix]['x']/1000,TZ)
  if (target-start).days>10: continue
  series=points[ix:]
  if any(p.get('unitMoney') for p in series[1:]): continue
  valid=True
  for a,b in zip(series,series[1:]):
   change=(b['y']/a['y']-1)*100; reported=number(b.get('equityReturn'))
   if reported is None or abs(change-reported)>0.08: valid=False; break
  if not valid: continue
  days=(end-start).total_seconds()/86400
  out['returns'][str(years)]=round(((series[-1]['y']/series[0]['y'])**(365.25/days)-1)*100,2)
  peak=series[0]['y']; dd=0
  for p in series:
   peak=max(peak,p['y']); dd=min(dd,(p['y']/peak-1)*100)
  out['drawdowns'][str(years)]=round(dd,2)
  out['periods'][str(years)]=[start.date().isoformat(),end.date().isoformat()]
 # Store small chart for 3y, with full-point drawdown above.
 cutoff=(end-dt.timedelta(days=3*365.25)).timestamp()*1000
 chart=[p for p in points if p['x']>=cutoff]
 if chart and '3' in out['returns']:
  step=max(1,len(chart)//80); sample=chart[::step]
  if sample[-1]!=chart[-1]: sample.append(chart[-1])
  out['chart']=[[dt.datetime.fromtimestamp(p['x']/1000,TZ).date().isoformat(),round((p['y']/chart[0]['y']-1)*100,2)] for p in sample]
 return out

def classify(target,scope,holdings):
 a=[x for x in holdings if re.fullmatch(r'(?:1\.(?:60|68)\d{4}|0\.(?:00|30)\d{4}|0\.92\d{4})',str(x))]
 if a: return 'a','披露的重仓股含 A 股：'+', '.join(a)+'。重仓代码接口未提供报告期，需核对季报。'
 # Direction grouping is explicitly provisional; never claim absence from top-ten holdings.
 if re.search(r'标[准普尔]*普?500|标准普尔500|纳斯达克100|纳斯达克 100|标普美国|MSCI美国|美国REIT',target,re.I):
  return 'us','跟踪标的：'+target+'。按美股指数方向初分；尚未完成全部持仓及合同的 A 股排除核验。'
 if target and target not in ['该基金无跟踪标的','无'] and re.search(r'恒生|日本|日经|德国|法国|欧洲|印度|越南|全球|海外|香港|富时100|韩国|东南亚',target):
  return 'overseas','跟踪标的：'+target+'。按海外方向初分；尚未证明完全不含 A 股。'
 return 'pending','不能仅凭名称或前十大持仓认定没有 A 股，待核对合同及完整定期报告。'

FIELDS = ('nav','returns','drawdowns','quota','purchase_fee','management','custody','service','redemption','structure','premium')
FIELD_KEYS = {
 'nav': ['nav','nav_date','nav_at'],
 'returns': ['returns','periods','chart','return_note','returns_date','returns_at'],
 'drawdowns': ['drawdowns','drawdown_periods','drawdowns_date','drawdowns_at'],
 'quota': ['quota','quota_raw','purchase_status','purchase_at'],
 'purchase_fee': ['purchase_fee','purchase_fee_at'],
 'redemption': ['redemption'],
 'structure': ['target','scope','benchmark','holdings','classification_note','detail_at','manager'],
 'premium': ['premium','price','iopv','quote_at','quote_date','quote_timestamp'],
}
DETAIL_FIELDS = ('management','custody','service','redemption','structure')
PURCHASE_URL = 'https://fund.eastmoney.com/Data/Fund_JJJZ_Data.aspx?t=8&page=1,50000&js=reData&sort=fcode,asc'

def cache_stamp(meta):
 return dt.datetime.fromtimestamp(meta['checked_at'],TZ).isoformat(timespec='seconds')

def source_keys(field,code):
 if field=='nav':return ['nav:'+code]
 if field in ('returns','drawdowns'):return ['history:'+code]
 if field in ('quota','purchase_fee'):return ['purchase']
 if field=='premium':return ['quotes']
 if field=='structure':return ['detail:'+code,'history:'+code]
 return ['detail:'+code]

def fail_field(f,field,error):
 clear_field(f,field,'error',str(error))
 meta=getattr(error,'meta',None)
 if not meta:
  for key in source_keys(field,f['code']):
   record=SOURCE_CACHE.read(key)
   if record and record.get('error'):meta=record;break
 if meta:
  f['field_states'][field].update(checked_at=cache_stamp(meta),next_retry_at=meta.get('retry_at'),cached=meta.get('cached',False))

def mark_source(f,field,meta):
 f['field_states'][field].update(checked_at=cache_stamp(meta),next_refresh_at=meta.get('expires_at'),cached=meta.get('cached',False))

def state(f,field,status,reason='',checked_at=None):
 f.setdefault('field_states',{})[field]={'status':status,'reason':reason,'checked_at':checked_at or now()}

def clear_field(f,field,status='loading',reason='正在获取'):
 if field in ('management','custody','service'): f.setdefault('fees',{}).pop(field,None)
 else:
  for key in FIELD_KEYS.get(field,[]): f.pop(key,None)
 if field=='structure': f['category']='pending'
 state(f,field,status,reason)

def field_value(f,field):
 if field in ('management','custody','service'): return f.get('fees',{}).get(field)
 if field=='structure': return f.get('scope') or f.get('target')
 if field=='quota': return f.get('purchase_status')
 return f.get(field)

def finish(f,field,reason='来源未提供数据'):
 value=field_value(f,field)
 state(f,field,'ok' if value is not None and value!='' and value!={} else 'missing',reason if value is None or value=='' or value=={} else '')

def _fetch_detail(code):
 # A manual request always re-fetches; raw files are evidence, never fallback values.
 s=fetch('https://fundf10.eastmoney.com/jbgk_'+code+'.html')
 if not cell(s,'基金代码') and not cell(s,'管理费率'): raise ValueError('详情结构无法识别')
 (CACHE/(code+'-detail.html')).write_text(s)
 fees={k:number((re.findall(r'[\d.]+',cell(s,v)) or [None])[0]) for k,v in [('management','管理费率'),('custody','托管费率'),('service','销售服务费率')]}
 return {'target':cell(s,'跟踪标的'),'scope':section(s,'投资范围'),'benchmark':cell(s,'业绩比较基准'),'fees':fees,'redemption':cell(s,'最高赎回费率'),'manager':cell(s,'基金管理人'),'detail_at':now()}

def _fetch_history(code):
 s=fetch('https://fund.eastmoney.com/pingzhongdata/'+code+'.js')
 if variable(s,'fS_code')!=code: raise ValueError('历史净值代码不匹配')
 result=performance(s)
 if 'nav_date' not in result: raise ValueError('没有有效历史净值序列')
 (CACHE/(code+'-nav.js')).write_text(s)
 result['holdings']=variable(s,'stockCodesNew') or []
 return result

def _fetch_latest_nav(code):
 url='https://api.fund.eastmoney.com/f10/lsjz?'+urllib.parse.urlencode({'fundCode':code,'pageIndex':1,'pageSize':1})
 raw=fetch(url); data=json.loads(raw)
 if data.get('ErrCode')!=0: raise ValueError('净值接口返回错误')
 rows=(data.get('Data') or {}).get('LSJZList') or []
 if not rows: raise ValueError('暂无已披露净值')
 row=rows[0]; value=number(row.get('DWJZ'));date=row.get('FSRQ','')
 if value is None or value<=0: raise ValueError('净值数值无效')
 try: dt.date.fromisoformat(date)
 except (ValueError,TypeError): raise ValueError('净值日期无效')
 (CACHE/(code+'-latest.json')).write_text(raw)
 return {'nav':value,'nav_date':date,'nav_at':now()}

def cached_dict(key,loader):
 value,meta=SOURCE_CACHE.get(key,loader);value['_cache']=meta;return value

def detail(code):return cached_dict('detail:'+code,lambda:_fetch_detail(code))
def history(code):return cached_dict('history:'+code,lambda:_fetch_history(code))
def latest_nav(code):return cached_dict('nav:'+code,lambda:_fetch_latest_nav(code))
def purchases():
 values,meta=SOURCE_CACHE.get('purchase',_fetch_purchases)
 for f in values:
  for field in ('quota','purchase_fee'):mark_source(f,field,meta)
 return values

def apply_history(f,h,fields):
 for field in fields:
  if field=='returns':
   f.update(returns=h['returns'],periods=h['periods'],return_note=h['return_note'],returns_date=h['nav_date'],returns_at=cache_stamp(h['_cache']) if h.get('_cache') else now())
   if h.get('chart'): f['chart']=h['chart']
  elif field=='drawdowns': f.update(drawdowns=h['drawdowns'],drawdown_periods=h['periods'],drawdowns_date=h['nav_date'],drawdowns_at=cache_stamp(h['_cache']) if h.get('_cache') else now())
  finish(f,field,'年限不足或分红 / 复权未通过校验')
  if h.get('_cache'):mark_source(f,field,h['_cache'])

def apply_detail(f,d,field,h=None):
 if field in ('management','custody','service'): f.setdefault('fees',{})[field]=d['fees'][field]
 elif field=='redemption': f['redemption']=d['redemption']
 elif field=='structure':
  for k in FIELD_KEYS['structure']:
   if k in d: f[k]=d[k]
  f['holdings']=h['holdings']
  f['category'],f['classification_note']=classify(f.get('target',''),f.get('scope',''),f['holdings'])
 finish(f,field)
 if d.get('_cache'):mark_source(f,field,d['_cache'])

def enrich(row,previous=None):
 # Inputs contain only fresh purchase/quote fields; each independent request clears its own fields.
 f=json.loads(json.dumps(row)); code=f['code']
 for field in ('nav','returns','drawdowns',*DETAIL_FIELDS): clear_field(f,field)
 try:
  nav=latest_nav(code);meta=nav.pop('_cache',None);f.update(nav);finish(f,'nav')
  if meta:mark_source(f,'nav',meta)
 except Exception as e: fail_field(f,'nav',e)
 h=None;history_error='';d=None;detail_error=''
 try:
  h=history(code);apply_history(f,h,('returns','drawdowns'))
 except Exception as e:
  history_error=str(e)
  for field in ('returns','drawdowns'): fail_field(f,field,e)
 try: d=detail(code)
 except Exception as e: detail_error=str(e)
 for field in DETAIL_FIELDS:
  if d is None: fail_field(f,field,detail_error)
  elif field=='structure' and h is None: fail_field(f,field,'持仓依据获取失败：'+history_error)
  else: apply_detail(f,d,field,h)
 return f

def atomic(data):
 tmp=DATA.with_suffix('.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))); tmp.replace(DATA)
def load():
 data=json.loads(DATA.read_text()) if DATA.exists() else {'funds':[]}
 for f in data['funds']:f['channel']=classify_channel(f)
 return data
def parse_rows(rows,stamp):
 result=[]
 for x in rows:
  if len(x)!=13: raise ValueError('申购数据字段结构变化')
  if 'QDII' not in x[2].upper() and '海外' not in x[2]: continue
  quota=number(x[9]); status=x[5]
  f={'code':x[0],'name':x[1],'type':x[2],'purchase_status':status,'quota_raw':quota,'quota':quota if status in ['限大额','开放申购'] and quota is not None and 0<quota<1e10 else None,'purchase_fee':x[12], 'purchase_at':stamp,'purchase_fee_at':stamp,'currency':'USD' if '美元' in x[1] or '现汇' in x[1] or '现钞' in x[1] else 'RMB','listed':status=='场内交易' or x[0].startswith(('15','16','50','51','52','56','58')),'category':'pending'}
  finish(f,'quota');finish(f,'purchase_fee');result.append(f)
 if len(result)<100: raise ValueError('候选覆盖异常')
 return result

def _fetch_purchases():
 s=fetch(PURCHASE_URL);return parse_rows(json.JSONDecoder().raw_decode(s[s.index('[['):])[0],now())

def _fetch_all_quotes():
 codes=sorted(f['code'] for f in load()['funds'] if f.get('listed'))
 items={}
 for i in range(0,len(codes),60):
  ids=','.join(('1.' if code[0] in '56' else '0.')+code for code in codes[i:i+60])
  data=json.loads(fetch('https://push2delay.eastmoney.com/api/qt/ulist.np/get?'+urllib.parse.urlencode({'secids':ids,'fltt':2,'invt':2,'fields':'f12,f2,f441,f297,f124'})))
  rows=(data.get('data') or {}).get('diff')
  if not isinstance(rows,list):raise ValueError('行情响应结构异常')
  items.update({q['f12']:q for q in rows})
 return items

def quotes(batch):
 if not batch:return
 try:
  items,meta=SOURCE_CACHE.get('quotes',_fetch_all_quotes)
  for f in batch:
   clear_field(f,'premium');q=items.get(f['code'],{});price=number(q.get('f2'));iopv=number(q.get('f441'))
   if price and iopv and iopv>0:
    f.update(premium=round((price/iopv-1)*100,2),price=price,iopv=iopv,quote_at=cache_stamp(meta),quote_date=q.get('f297'),quote_timestamp=q.get('f124'));finish(f,'premium')
   else:state(f,'premium','missing','来源未提供有效价格 / IOPV')
   mark_source(f,'premium',meta)
 except Exception as e:
  for f in batch:fail_field(f,'premium',e)

def summarize(data):
 states=[v for f in data['funds'] for v in f.get('field_states',{}).values()]
 data['schema_version']=2;data['error_count']=sum(v['status']=='error' for v in states)
 data['message']='网站数据共享；有效期内直接使用，过期才请求上游，失败项按冷却时间重试'

def seed_source_cache(data):
 """Initialize from complete successful site snapshots, retaining original check times."""
 def timestamp(f,fields):
  times=[]
  for field in fields:
   info=f.get('field_states',{}).get(field,{})
   if info.get('status')!='ok' or not info.get('checked_at'):return None
   try:times.append(dt.datetime.fromisoformat(info['checked_at']).timestamp())
   except ValueError:return None
  return min(times)
 def seed(key,value,stamp):
  if stamp and SOURCE_CACHE.read(key) is None:
   SOURCE_CACHE.write(key,{'value':value,'checked_at':stamp,'expires_at':stamp+TTLS[key.split(':')[0]],'failures':0})
 for f in data['funds']:
  code=f['code'];stamp=timestamp(f,('nav',))
  if f.get('nav') is not None and f.get('nav_date'):
   seed('nav:'+code,{k:f[k] for k in ('nav','nav_date','nav_at') if k in f},stamp)
  stamp=timestamp(f,('returns','drawdowns','structure'))
  if f.get('returns_date') and f.get('returns_date')==f.get('drawdowns_date') and f.get('holdings') is not None:
   h={k:f.get(k,{}) for k in ('returns','drawdowns','periods')};h.update(nav_date=f['returns_date'],return_note=f.get('return_note',''),holdings=f['holdings'])
   if f.get('chart'):h['chart']=f['chart']
   seed('history:'+code,h,stamp)
  stamp=timestamp(f,DETAIL_FIELDS)
  if stamp:seed('detail:'+code,{k:f.get(k,'') for k in ('fees','redemption','target','scope','benchmark','manager','detail_at')},stamp)
 entries=[];stamps=[]
 for f in data['funds']:
  stamp=timestamp(f,('quota','purchase_fee'))
  if not stamp:break
  fields=('code','name','type','currency','listed','purchase_status','quota','quota_raw','purchase_fee','purchase_at','purchase_fee_at')
  entry={k:f.get(k) for k in fields};entry['category']='pending';entry['field_states']={k:f['field_states'][k] for k in ('quota','purchase_fee')};entries.append(entry);stamps.append(stamp)
 if len(entries)==len(data['funds']) and len(entries)>=100:seed('purchase',entries,min(stamps))

def bootstrap():
 if not DATA.exists() and (ROOT/'web/data.json').exists():DATA.write_text((ROOT/'web/data.json').read_text())
 data=load()
 if not DATA.exists():
  rows=list(csv.reader(open(ROOT/'data/qdii_candidates.csv',encoding='utf-8-sig')))[1:]
  data={'funds':parse_rows(rows,'2026-09-11T00:38:00+08:00')}
 if data.get('schema_version')==2:
  changed=False
  for f in data['funds']:
   for field,info in list(f.get('field_states',{}).items()):
    if info['status']=='loading':clear_field(f,field,'error','上次请求已中断，请重试');changed=True
  if changed:summarize(data);atomic(data)
  seed_source_cache(data)
  return
 # Legacy errors cannot identify the failed detail request. Discard all values from that combined group.
 for f in data['funds']:
  had_error=f.pop('error',None);quote_error=f.pop('quote_error',None)
  f['returns_date']=f.get('nav_date');f['drawdowns_date']=f.get('nav_date');f['drawdown_periods']=f.get('periods',{})
  for field in FIELDS:
   if had_error and field in ('nav','returns','drawdowns',*DETAIL_FIELDS):clear_field(f,field,'error','旧版合并请求失败，旧值已移除，请单项重试')
   elif field=='premium' and quote_error:clear_field(f,field,'error','行情更新失败，旧值已移除')
   elif field=='premium' and not f.get('listed'):state(f,field,'na','非上市份额不适用')
   else:
    finish(f,field)
    stamp=f.get('quote_at') if field=='premium' else f.get('purchase_at') if field in ('quota','purchase_fee') else f.get('detail_at') if field in DETAIL_FIELDS else f.get('metrics_at')
    f['field_states'][field]['checked_at']=stamp
  f.pop('metrics_at',None)
 summarize(data);atomic(data)

def refresh(limit=None):
 if not LOCK.acquire(False):return False
 STATUS.update(running=True,done=0,total=0,errors=0,message='正在逐项刷新')
 data=load()
 try:
  try:
   fresh=purchases()
   old_by_code={f['code']:f for f in data['funds']}
   for f in fresh:
    old=old_by_code.get(f['code'],{})
    # Purchase source updates only its own fields; preserve other source snapshots.
    combined=json.loads(json.dumps(old));states=combined.get('field_states',{});states.update(f.get('field_states',{}))
    category=combined.get('category','pending');combined.update(f);combined['category']=category;combined['field_states']=states;f.update(combined)
   data['funds']=fresh;data['purchase_at']=fresh[0].get('purchase_at') if fresh else None
  except Exception as e:
   for f in data['funds']:
    for field in ('quota','purchase_fee'):fail_field(f,field,e)
  atomic(data);funds=data['funds'];listed=[f for f in funds if f.get('listed')]
  for i in range(0,len(listed),60):quotes(listed[i:i+60])
  atomic(data);ordered=funds[:limit] if limit else funds
  STATUS['total']=len(ordered)
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
   jobs=[pool.submit(enrich,f) for f in ordered];positions={f['code']:i for i,f in enumerate(funds)}
   for job in concurrent.futures.as_completed(jobs):
    f=job.result();funds[positions[f['code']]]=f;STATUS['done']+=1
    STATUS['errors']=sum(v['status']=='error' for item in funds for v in item.get('field_states',{}).values())
    if STATUS['done']%6==0:atomic(data)
  for f in funds:
   for field,info in list(f.get('field_states',{}).items()):
    if info['status']=='loading':clear_field(f,field,'missing','本轮未请求，可单项获取')
  data['completed_at']=now();summarize(data);atomic(data);STATUS['message']='已获取网站最新数据；有效缓存已复用，失败项进入冷却'
 except Exception as e:
  for f in data['funds']:
   for field,info in list(f.get('field_states',{}).items()):
    if info['status']=='loading':clear_field(f,field,'error','刷新中断：'+str(e))
  summarize(data);atomic(data);STATUS['errors']=data['error_count'];STATUS['message']='刷新中断，未完成项已清空'
 finally:STATUS['running']=False;LOCK.release()
 return True

def retry(code,field):
 if field not in FIELDS or not re.fullmatch(r'\d{6}',code):return {'error':'无效基金代码或数据项'},400
 if not LOCK.acquire(False):return {'joined':True,'message':'已有共享刷新任务，正在等待其结果'},202
 try:
  STATUS.update(running=True,done=0,total=1,message='正在检查共享数据')
  data=load();f=next((x for x in data['funds'] if x['code']==code),None)
  if f is None:return {'error':'基金不在候选列表中'},404
  # Fees share the purchase source, but a fee-only click does not shorten its 24h interval.
  if field=='purchase_fee':
   info=f.get('field_states',{}).get(field,{})
   try:fresh=info.get('status')=='ok' and time.time()-dt.datetime.fromisoformat(info['checked_at']).timestamp()<86400
   except (ValueError,KeyError,TypeError):fresh=False
   if fresh:
    info['cached']=True
    return {'fund':f,'field':field,'state':info},200
  try:
   if field=='nav':
    nav=latest_nav(code);meta=nav.pop('_cache',None);clear_field(f,field);f.update(nav);finish(f,field)
    if meta:mark_source(f,field,meta)
   elif field in ('returns','drawdowns'):
    h=history(code)
    for item in ('returns','drawdowns'):clear_field(f,item)
    apply_history(f,h,('returns','drawdowns'))
   elif field in ('quota','purchase_fee'):
    fresh=next((x for x in purchases() if x['code']==code),None)
    if fresh is None:raise ValueError('来源未返回该基金')
    for item in ('quota','purchase_fee'):
     clear_field(f,item)
     for key in FIELD_KEYS[item]:
      if key in fresh:f[key]=fresh[key]
     f['field_states'][item]=fresh['field_states'][item]
   elif field=='premium':
    if f.get('listed'):quotes([f])
    else:state(f,field,'na','非上市份额不适用')
   else:
    d=detail(code)
    for item in ('management','custody','service','redemption'):
     clear_field(f,item);apply_detail(f,d,item)
    if field=='structure':
     h=history(code);clear_field(f,field);apply_detail(f,d,field,h)
  except Exception as e:
   related=('returns','drawdowns') if field in ('returns','drawdowns') else ('management','custody','service','redemption') if field in ('management','custody','service','redemption') else (field,)
   for item in related:fail_field(f,item,e)
  summarize(data);atomic(data)
  return {'fund':f,'field':field,'state':f['field_states'][field]},200
 finally:
  STATUS.update(running=False,done=1,message='已获取网站最新数据');LOCK.release()

class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k): super().__init__(*a,directory=str(ROOT/'web'),**k)
 def log_message(self,*a): pass
 def send_json(self,x,status=200):
  body=json.dumps(x,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.path.startswith('/api/export?'):
   params=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query); codes=set(params.get('codes',[''])[0].split(','));years=params.get('years',['3'])[0]
   out=io.StringIO();w=csv.writer(out);w.writerow(['代码','名称','币种','方向初分','分类依据',years+'年年化%',years+'年最大回撤%','基金净值','净值截止日','交易渠道（初分）','场外申购状态','场外日申购限额','平台申购费','管理费%','托管费%','销售服务费%','IOPV溢价%','行情日期','额度抓取','指标抓取','更新错误'])
   for f in load()['funds']:
    if f['code'] not in codes: continue
    values=[f['code'],f['name'],f['currency'],f['category'],f.get('classification_note'),f.get('returns',{}).get(years),f.get('drawdowns',{}).get(years),f.get('nav'),f.get('nav_date'),CHANNEL_LABELS[classify_channel(f)],f.get('purchase_status'),f.get('quota'),f.get('purchase_fee'),*[f.get('fees',{}).get(k) for k in ['management','custody','service']],f.get('premium'),f.get('quote_date'),f.get('purchase_at'),f.get('returns_at'),json.dumps(f.get('field_states',{}),ensure_ascii=False)]
    w.writerow([("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for v in values])
   body=('\ufeff'+out.getvalue()).encode('utf-8');self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename="fund-atlas.csv"');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
  if self.path=='/api/status': return self.send_json(STATUS.copy())
  if self.path in ('/api/data','/data.json'): return self.send_json(load())
  return super().do_GET()
 def do_POST(self):
  if self.path not in ('/api/refresh','/api/retry'): return self.send_json({'error':'Not found'},404)
  origin=self.headers.get('Origin')
  if origin and origin not in [*ALLOWED_ORIGINS]: return self.send_json({'error':'Origin rejected'},403)
  if self.path=='/api/retry':
   try:
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=1024:raise ValueError()
    payload=json.loads(self.rfile.read(length));code=payload.get('code','');field=payload.get('field','')
    if not isinstance(code,str) or not isinstance(field,str):raise ValueError()
   except (ValueError,AttributeError):return self.send_json({'error':'无效请求'},400)
   result,status=retry(code,field);return self.send_json(result,status)
  if LOCK.locked():return self.send_json({'accepted':True,'joined':True},202)
  threading.Thread(target=refresh,daemon=True).start()
  self.send_json({'accepted':True},202)
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');p.add_argument('--limit',type=int); args=p.parse_args()
 import fcntl
 process_lock=(RUNTIME/'server.lock').open('a')
 try:fcntl.flock(process_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('已有服务使用该数据目录，请通过网页刷新，勿启动第二个进程')
 bootstrap()
 if args.refresh:
  refresh(args.limit);print(json.dumps(STATUS,ensure_ascii=False))
 else:
  print('Fund Atlas: http://127.0.0.1:8765',flush=True);ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
