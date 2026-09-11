#!/usr/bin/env python3
"""Analyze saved test_qdii_api.py responses without executing remote JavaScript."""
import csv,json,re,collections,pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent; raw=ROOT/'work/api-probe'; out=ROOT/'work/research'
out.mkdir(parents=True,exist_ok=True)
def read(n): return (raw/(n+'.txt')).read_text(encoding='utf-8-sig')
def array(n):
 s=read(n); return json.JSONDecoder().raw_decode(s[s.index('[['):])[0]
a=array('purchase'); candidates=[x for x in a if 'QDII' in x[2].upper() or '海外' in x[2]]
cols=['基金代码','基金简称','基金类型','净值','净值日期_原始月日','申购状态','赎回状态','下一开放日','购买起点_原始','日累计限额_原始','原始字段10','原始字段11','手续费']
assert all(len(x)==len(cols) for x in a), 'Subscription schema changed'
with (out/'qdii_candidates.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(cols);w.writerows(candidates)
j=json.loads(read('jisilu_unauth')); cells=[x['cell'] for x in j['rows']]
(out/'jisilu_sample.json').write_text(json.dumps(cells,ensure_ascii=False,indent=2))
quotes=json.loads(read('etf_selected'))['data']['diff']
for x in quotes:
 x['calculated_iopv_premium_pct']=round((x['f2']/x['f441']-1)*100,4)
 x['sign_check_error_pp']=round(x['calculated_iopv_premium_pct']+x['f402'],4)
(out/'etf_sample.json').write_text(json.dumps(quotes,ensure_ascii=False,indent=2))
s=read('fund_performance_161125'); m=re.search(r'var\s+Data_netWorthTrend\s*=\s*',s); trend=json.JSONDecoder().raw_decode(s[m.end():])[0]
summary={'all_subscription_rows':len(a),'QDII_label_rows':sum('QDII' in x[2].upper() for x in a),'overseas_index_rows':sum(x[2]=='指数型-海外股票' for x in a),'candidate_rows':len(candidates),'candidate_status_counts':dict(collections.Counter(x[5] for x in candidates)),'jsl_rows':len(cells),'jsl_warning':j.get('warn'),'jsl_missing_fields':{k:sum(x.get(k) in [None,'','-'] for x in cells) for k in ['estimate_value','discount_rt','nav_discount_rt','index_nm','apply_status']},'history_161125_points':len(trend),'history_first':trend[0],'history_last':trend[-1],'performance_raw_vars':dict(re.findall(r'var (syl_\w+)\s*=\s*([^;]+)',s))}
(out/'data_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
