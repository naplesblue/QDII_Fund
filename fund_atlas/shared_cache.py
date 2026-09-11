"""Persistent, process-safe cache. One upstream request per source key, even across processes."""
import datetime as dt
import fcntl
import hashlib
import json
import pathlib
import sqlite3
import threading
import time
from contextlib import contextmanager

TZ = dt.timezone(dt.timedelta(hours=8))
TTLS = {'nav': 21600, 'history': 86400, 'detail': 86400, 'purchase': 1800, 'quotes': 300}
BACKOFF = (300, 900, 1800, 3600)
HOLIDAYS = {
 2026: [('01-01','01-03'),('02-15','02-23'),('04-04','04-06'),('05-01','05-05'),('06-19','06-21'),('09-25','09-27'),('10-01','10-07')]
}
# Source: https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml

def trading_day(day):
 return day.year in HOLIDAYS and day.weekday()<5 and not any(a<=day.strftime('%m-%d')<=b for a,b in HOLIDAYS[day.year])

def quote_session(timestamp):
 """Session id bounds the quote-cache window. Closed-market clicks cannot poll repeatedly."""
 date=dt.datetime.fromtimestamp(timestamp,TZ);day=date.date();minutes=date.hour*60+date.minute
 if day.year not in HOLIDAYS:return 'calendar-unknown',False
 if trading_day(day):
  if 570<=minutes<690 or 780<=minutes<900:return day.isoformat(),True
  if minutes>=900:return day.isoformat(),False
  if minutes>=690:return day.isoformat()+'-lunch',False
 for days in range(1,370):
  previous=day-dt.timedelta(days=days)
  if trading_day(previous):return previous.isoformat(),False
 return 'calendar-unknown',False

class CacheFailure(Exception):
 def __init__(self, message, meta):
  super().__init__(message);self.meta=meta

class SharedCache:
 def __init__(self,directory,clock=time.time):
  self.directory=pathlib.Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
  self.db=self.directory/'sources.sqlite3';self.clock=clock;self.guard=threading.Lock();self.locks={}
  with self.connect() as db:
   db.execute('CREATE TABLE IF NOT EXISTS source_cache (key TEXT PRIMARY KEY, record TEXT NOT NULL)')
 @contextmanager
 def connect(self):
  db=sqlite3.connect(self.db,timeout=30)
  try:
   with db:yield db
  finally:db.close()
 @contextmanager
 def key_lock(self,key):
  with self.guard:lock=self.locks.setdefault(key,threading.Lock())
  with lock:
   path=self.directory/(hashlib.sha256(key.encode()).hexdigest()+'.lock')
   with path.open('a') as handle:
    fcntl.flock(handle,fcntl.LOCK_EX)
    try:yield
    finally:fcntl.flock(handle,fcntl.LOCK_UN)
 def read(self,key):
  with self.connect() as db:row=db.execute('SELECT record FROM source_cache WHERE key=?',(key,)).fetchone()
  return json.loads(row[0]) if row else None
 def write(self,key,value):
  with self.connect() as db:db.execute('INSERT OR REPLACE INTO source_cache VALUES (?,?)',(key,json.dumps(value,ensure_ascii=False)))
 def fresh(self,key,record,now):
  if not record:return False
  if record.get('error'):return now<record['retry_at']
  if key=='quotes':
   session,active=quote_session(now)
   if active and record.get('session')!=session:return False
   if not active:
    return record.get('session')==session and record.get('closed_snapshot',False)
  return now<record['expires_at']
 def peek(self,key):
  record=self.read(key)
  if record and self.fresh(key,record,self.clock()):return record
  return None
 def get(self,key,loader):
  with self.key_lock(key):
   now=self.clock();old=self.read(key)
   if self.fresh(key,old,now):
    meta={k:v for k,v in old.items() if k!='value'};meta['cached']=True
    if old.get('error'):raise CacheFailure(old['error'],meta)
    return old['value'],meta
   if key=='quotes' and quote_session(now)[0]=='calendar-unknown':
    raise CacheFailure('交易日历未配置，暂停行情请求',{'cached':True,'checked_at':now,'retry_at':now+86400})
   try:value=loader()
   except Exception as exc:
    now=self.clock();failures=(old or {}).get('failures',0)+1
    record={'error':str(exc),'checked_at':now,'retry_at':now+BACKOFF[min(failures-1,len(BACKOFF)-1)],'failures':failures}
    self.write(key,record)
    raise CacheFailure(str(exc),dict(record,cached=False)) from exc
   now=self.clock();kind=key.split(':')[0]
   session,active=quote_session(now) if kind=='quotes' else ('',False)
   record={'value':value,'checked_at':now,'expires_at':now+TTLS[kind],'failures':0,'session':session,'closed_snapshot':kind=='quotes' and not active}
   self.write(key,record)
   return value,dict((k,v) for k,v in record.items() if k!='value')|{'cached':False}
