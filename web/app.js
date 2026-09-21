'use strict';
const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const channelLabels={exchange:'场内买卖',otc:'场外申购',both:'两者均可',unknown:'渠道待核验'};
const labels={all:'全部候选',us:'纯美股方向',overseas:'其他海外方向',a:'含 A 股',pending:'待核验'};
let dataset={funds:[]},category='all',years='3',page=1,filtered=[],timer=null,sortKey='return',sortDirection='desc';
const retrying=new Set();let detailCode=null,cooldownTimer=null;
let favorites=new Set();try{favorites=new Set(JSON.parse(localStorage.getItem('fund-atlas-favorites')||'[]'))}catch{}
const pct=n=>n===null||n===undefined?'待核验':`${n.toFixed(2)}%`;
const stamp=s=>s?new Date(s).toLocaleString('zh-CN',{hour12:false}):'暂无';
function quota(f){if(f.purchase_status==='暂停申购')return '暂停申购';if(f.purchase_status==='场内交易')return f.channel==='exchange'?'不适用':'未披露';if(!['限大额','开放申购'].includes(f.purchase_status))return f.purchase_status||'待核验';return f.quota?`${f.currency==='USD'?'$':'¥'}${f.quota.toLocaleString('zh-CN')}`:'额度待核验'}
function val(f,type){if(type==='return')return f.returns?.[years];if(type==='drawdown')return f.drawdowns?.[years]==null?undefined:Math.abs(f.drawdowns[years]);if(type==='fee')return f.fees?.management;if(type==='purchase_fee'){const match=String(f.purchase_fee??'').trim().match(/^(\d+(?:\.\d+)?)%$/);return match?Number(match[1]):undefined}return f[type]}
function activeFilters(f){const q=$('search').value.toLowerCase().trim();const c=$('channel').value,fc=f.channel||'unknown';if(c!=='all'&&!(c===fc||(['exchange','otc'].includes(c)&&fc==='both')))return false;if(category!=='all'&&f.category!==category)return false;if($('currency').value!=='all'&&f.currency!==$('currency').value)return false;if(q&&!`${f.name} ${f.code} ${f.target||''}`.toLowerCase().includes(q))return false;if($('available').checked&&(!['otc','both'].includes(fc)||!['开放申购','限大额'].includes(f.purchase_status)))return false;if($('starred').checked&&!favorites.has(f.code))return false;for(const [id,value,direction] of [['minQuota',f.quota,1],['minReturn',f.returns?.[years],1],['maxFee',f.fees?.management,-1],['maxPremium',f.premium,-1]]){const s=$(id).value;if(s!==''&&(value==null||(direction===1?value<Number(s):value>Number(s))))return false}return true}
const fieldLabels={nav:'基金净值',returns:'年化收益',drawdowns:'最大回撤',quota:'场外申购限额',purchase_fee:'申购费',management:'管理费',custody:'托管费',service:'销售服务费',redemption:'赎回费',structure:'投资结构',premium:'场内溢价'};
function missingCell(f,field,fallback='来源未提供'){
 const info=f.field_states?.[field]||{},busy=retrying.has(f.code+':'+field)||info.status==='loading';
 const cooling=info.next_retry_at*1000>Date.now();
 const reason=info.reason||fallback,label=cooling?'冷却至 '+new Date(info.next_retry_at*1000).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false}):field==='structure'?(busy?'投资结构获取中…':info.status==='error'?'投资结构获取失败':fallback):(busy?'获取中…':info.status==='error'?'获取失败':fallback);
 return `<div class="field-missing ${info.status==='error'?'field-error':''}" title="${esc(reason)}"><span>${esc(label)}</span><button class="field-retry" data-retry="${field}" data-code="${f.code}" title="重新获取${fieldLabels[field]}" aria-label="重新获取 ${esc(f.name)} 的${fieldLabels[field]}" ${busy||cooling?'disabled':''}><span aria-hidden="true">${busy?'…':'↻'}</span><span class="retry-text">${busy?'请稍候':'重试'}</span></button></div>`;
}
function metricCell(f,field,value,sub='',fallback='来源未提供'){
 const info=f.field_states?.[field]||{};
 if(info.status==='na')return '<span class="dim">不适用</span>';
 if(['loading','error'].includes(info.status)||value==null||value==='')return missingCell(f,field,fallback);
 return `<span title="获取时间：${esc(stamp(info.checked_at))}${sub?' · 数据日期 / 说明：'+esc(sub):''}">${value}</span>${sub?`<small>${esc(sub)}</small>`:''}`;
}
function quotaCell(f){
 if(f.channel==='exchange')return '<span class="dim" title="ETF 一级市场申赎另有门槛，不属于场外申购额度">不适用</span>';
 const legitimate=f.purchase_status&& !['限大额','开放申购'].includes(f.purchase_status);
 return metricCell(f,'quota',f.quota!=null||legitimate?esc(quota(f)):null,f.quota?`${f.currency} · ${f.purchase_status}`:f.currency,'额度未披露');
}
function fieldCards(f){return [
 ['nav',f.nav==null?null:f.nav.toFixed(4),f.nav_date],
 ['returns',f.returns?.[years]==null?null:pct(f.returns[years]),f.returns_date],
 ['drawdowns',f.drawdowns?.[years]==null?null:pct(f.drawdowns[years]),f.drawdowns_date],
 ['management',f.fees?.management==null?null:pct(f.fees.management),'每年'],
 ['custody',f.fees?.custody==null?null:pct(f.fees.custody),'每年'],
 ['service',f.fees?.service==null?null:pct(f.fees.service),'每年']
 ].map(([key,value,sub])=>`<div class="metric"><span>${fieldLabels[key]}${['returns','drawdowns'].includes(key)?' · '+years+' 年':''}</span><div class="metric-value">${metricCell(f,key,value,sub,['returns','drawdowns'].includes(key)?'年限 / 复权待核验':'来源未提供')}</div></div>`).join('')}
function clearClientField(f,field){
 const keys={nav:['nav','nav_date'],returns:['returns','periods','chart','returns_date'],drawdowns:['drawdowns','drawdown_periods','drawdowns_date'],quota:['quota','quota_raw','purchase_status'],purchase_fee:['purchase_fee'],premium:['premium','price','iopv','quote_date'],structure:['target','scope','benchmark','holdings','classification_note'],redemption:['redemption']}[field]||[];
 keys.forEach(k=>delete f[k]);if(['management','custody','service'].includes(field)&&f.fees)delete f.fees[field];if(field==='structure')f.category='pending';
}
async function retryField(code,field){
 if(retrying.size)return;
 const f=dataset.funds.find(x=>x.code===code);if(!f)return;
 // The server independently clears and persists the same field before its request.
 // A cache check does not invalidate valid shared values.
 retrying.add(code+':'+field);$('refresh').disabled=true;render();if(detailCode===code)showDetail(code);
 try{
  const response=await fetch('/api/retry',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,field})});const result=await response.json();
  if(response.status===202&&result.joined){message('正在等待共享刷新结果，不会重复请求上游');clearTimeout(timer);timer=setTimeout(checkStatus,500);return}
  if(!response.ok){if(response.status===409)await loadData();throw Error(result.error||'本地服务请求失败')}
  const index=dataset.funds.findIndex(x=>x.code===code);dataset.funds[index]=result.fund;
  const info=result.state;message(`${fieldLabels[field]}：${info.status==='ok'?(info.cached?'已使用网站共享数据，未重复请求上游':'已更新'):info.status==='na'?'不适用':info.reason||'来源未提供'} · ${f.name}`,info.status==='error');
 }catch(error){
  const current=dataset.funds.find(x=>x.code===code);
  if(current?.field_states?.[field]?.status==='loading'){clearClientField(current,field);current.field_states[field]={status:'error',reason:error.message}}
  message(error.message,true);
 }finally{retrying.clear();$('refresh').disabled=false;render();if(detailCode===code&&$('detail').open)showDetail(code)}
}
function render(){
 $('total').textContent=dataset.funds.length.toLocaleString();const counts={all:dataset.funds.length,us:0,overseas:0,a:0,pending:0};dataset.funds.forEach(f=>counts[f.category||'pending']++);Object.entries(counts).forEach(([k,v])=>$('count-'+k).textContent=v);
 const complete=dataset.funds.filter(f=>f.nav!=null).length;$('coverage').textContent=`净值覆盖 ${complete} / ${dataset.funds.length}`;$('stamp').textContent=`批量额度抓取 ${stamp(dataset.purchase_at)}`;
 filtered=dataset.funds.filter(activeFilters);filtered.sort((a,b)=>{const av=val(a,sortKey),bv=val(b,sortKey);if(av==null)return bv==null?a.code.localeCompare(b.code):1;if(bv==null)return -1;return (sortDirection==='desc'?bv-av:av-bv)||a.code.localeCompare(b.code)});
 const pages=Math.max(1,Math.ceil(filtered.length/15));page=Math.min(page,pages);$('sectionTitle').textContent=labels[category];$('resultCount').textContent=`${filtered.length} 个匹配份额 · 点击基金名称查看依据`;$('returnHeading').textContent=`${years} 年年化`;$('ddHeading').textContent=`${years} 年回撤`;
 const sortLabels={nav:'基金净值',return:years+' 年年化',drawdown:years+' 年最大回撤',quota:'场外申购限额',purchase_fee:'申购费',fee:'管理费',premium:'场内溢价'};
 document.querySelectorAll('[data-sort]').forEach(button=>{const active=button.dataset.sort===sortKey;button.closest('th').setAttribute('aria-sort',active?(sortDirection==='asc'?'ascending':'descending'):'none');button.classList.toggle('active',active);button.querySelector('.sort-arrow').textContent=active?(sortDirection==='asc'?'↑':'↓'):'↕';const next=active?(sortDirection==='asc'?'降序':'升序'):(['return','quota'].includes(button.dataset.sort)?'降序':'升序');button.setAttribute('aria-label',sortLabels[button.dataset.sort]+'，点击按'+(button.dataset.sort==='drawdown'?'回撤幅度':'数值')+next+'排列');button.title=button.dataset.sort==='drawdown'?'按回撤幅度排序：升序时 −10% 排在 −20% 前':'点击切换升序 / 降序';});
 $('sortStatus').textContent=`${sortLabels[sortKey]} · ${sortDirection==='asc'?'升序 ↑':'降序 ↓'}${sortKey==='drawdown'?'（按回撤幅度）':''} · 点击表头切换方向，非数值项始终置后`;
 $('rows').innerHTML=filtered.slice((page-1)*15,page*15).map(f=>{const r=f.returns?.[years],dd=f.drawdowns?.[years];return `<tr><td><button class="fund-name" data-detail="${f.code}">${esc(f.name)}</button><div class="fund-meta"><span class="code">${f.code}</span><span class="tag ${f.category}">${labels[f.category]||'待核验'}</span><span class="tag channel-tag" title="按份额类型初分；是否开放以最新公告及销售渠道为准">${channelLabels[f.channel]||channelLabels.unknown}</span></div>${['error','missing','loading'].includes(f.field_states?.structure?.status)?missingCell(f,'structure','结构待核验'):''}</td><td>${metricCell(f,'nav',f.nav==null?null:f.nav.toFixed(4),f.nav_date,'净值未披露')}</td><td class="${r==null?'dim':r>=0?'positive':'negative'}">${metricCell(f,'returns',r==null?null:`${r>0?'+':''}${pct(r)}`,f.returns_date,'年限 / 复权待核验')}</td><td class="${dd==null?'dim':'negative'}">${metricCell(f,'drawdowns',dd==null?null:pct(dd),f.drawdowns_date,'年限 / 复权待核验')}</td><td>${quotaCell(f)}</td><td>${metricCell(f,'purchase_fee',f.purchase_fee?esc(f.purchase_fee):null)}</td><td>${metricCell(f,'management',f.fees?.management==null?null:pct(f.fees.management))}</td><td class="${f.premium!=null&&f.premium>3?'negative':'dim'}">${metricCell(f,'premium',f.premium==null?null:pct(f.premium),f.quote_date,'暂无有效 IOPV')}</td><td><button class="star ${favorites.has(f.code)?'saved':''}" data-star="${f.code}" aria-label="${favorites.has(f.code)?'取消关注':'关注'} ${esc(f.name)}" aria-pressed="${favorites.has(f.code)}">${favorites.has(f.code)?'★':'☆'}</button></td></tr>`}).join('');
 document.querySelectorAll('#rows tr').forEach(row=>{
 const names=['基金', '基金净值', years+' 年年化',years+' 年最大回撤','场外申购限额','申购费','管理费 / 年','场内溢价','关注'];
 Array.from(row.children).forEach((cell,i)=>cell.dataset.label=names[i]);
 const fund=dataset.funds.find(f=>f.code===row.querySelector('[data-detail]')?.dataset.detail);
 if(fund){if(fund.returns_date===fund.nav_date)row.children[2].querySelector('small')?.classList.add('same-date');if(fund.drawdowns_date===fund.nav_date)row.children[3].querySelector('small')?.classList.add('same-date');}
 });
 clearTimeout(cooldownTimer);const due=dataset.funds.flatMap(f=>Object.values(f.field_states||{}).map(s=>s.next_retry_at*1000)).filter(t=>t>Date.now());if(due.length)cooldownTimer=setTimeout(render,Math.min(2147483647,Math.max(500,Math.min(...due)-Date.now()+50)));
 $('empty').hidden=filtered.length>0;$('pageInfo').textContent=filtered.length?`显示 ${(page-1)*15+1} 至 ${Math.min(page*15,filtered.length)} / ${filtered.length}`:'0 个结果';$('pageNumber').textContent=`${page} / ${pages}`;$('prev').disabled=page===1;$('next').disabled=page===pages;
 document.querySelectorAll('[data-cat]').forEach(b=>{b.classList.toggle('active',b.dataset.cat===category);b.setAttribute('aria-pressed',b.dataset.cat===category)});document.querySelectorAll('[data-years]').forEach(b=>{b.classList.toggle('selected',b.dataset.years===years);b.setAttribute('aria-pressed',b.dataset.years===years)});
}
function historyChart(f){
 if(!f.chart?.length)return '';
 const values=f.chart.map(p=>p[1]),lo=Math.min(...values),hi=Math.max(...values),range=hi-lo||1;
 const points=values.map((v,i)=>`${i/Math.max(1,values.length-1)*650},${115-(v-lo)/range*100}`).join(' ');
 return `<div class="detail-section"><h3>近 3 年净值区间表现 · 采样展示</h3><svg class="detail-chart" viewBox="0 0 650 130" preserveAspectRatio="none" role="img" aria-label="近三年净值区间表现"><polyline points="${points}" fill="none" stroke="#23654d" stroke-width="2.5"/></svg><p>${esc(f.chart[0][0])} 至 ${esc(f.chart.at(-1)[0])} · 起点归零</p></div>`;
}
function showDetail(code){
 const f=dataset.funds.find(x=>x.code===code);if(!f)return;detailCode=code;
 const timestamps=Object.entries(fieldLabels).map(([key,label])=>{const info=f.field_states?.[key];return `${label}：${stamp(info?.checked_at)}${info?.reason?' · '+esc(info.reason):''}`}).join('<br>');
 $('detailContent').innerHTML=`<h2>${esc(f.name)}</h2><div class="detail-sub">${f.code} · ${esc(f.currency)} · ${esc(f.type)} · ${channelLabels[f.channel]||channelLabels.unknown}</div><p class="channel-note">交易渠道按份额类型初分，暂停申购不会改变渠道归类。ETF 一级市场申购另有最小单位和限额，本页尚未接入实时申赎清单；LOF 场内申购额度不能由场外额度推断。</p><div class="detail-grid">${fieldCards(f)}</div>${historyChart(f)}<div class="detail-section"><h3>投资结构 · ${labels[f.category]}</h3>${metricCell(f,'structure',f.scope||f.target?esc(f.classification_note||'方向待核验'):null)}<p>基准：${esc(f.benchmark||'未获取')}</p><p>投资范围：${esc(f.scope||'未获取')}</p></div><div class="detail-section"><h3>购买与交易费用</h3><div class="detail-grid"><div class="metric"><span>场外申购限额</span>${quotaCell(f)}</div><div class="metric"><span>平台申购费</span>${metricCell(f,'purchase_fee',f.purchase_fee?esc(f.purchase_fee):null)}</div><div class="metric"><span>最高赎回费</span>${metricCell(f,'redemption',f.redemption?esc(f.redemption):null)}</div><div class="metric"><span>场内 IOPV 溢价</span>${metricCell(f,'premium',f.premium==null?null:pct(f.premium),f.quote_date,'暂无有效 IOPV')}</div></div><p>实际赎回费按持有天数查费率表；券商佣金因账户而异。联接基金的底层费用与豁免规则须查合同。额度未验证具体渠道、账户合并及定投规则。</p></div><div class="detail-section"><h3>数据口径与时间</h3><p>净值是最新披露值，非实时估值；每项单独记录抓取时间。有效期内复用网站数据；失败项不保留旧值，并按冷却时间重试。同一来源的关联指标共享一次请求。</p><p>${esc(f.return_note||'历史收益尚未完成核验。')}<br>收益区间：${esc(f.periods?.[years]?.join(' 至 ')||'未计算')}<br>回撤区间：${esc(f.drawdown_periods?.[years]?.join(' 至 ')||'未计算')}</p><p>${timestamps}</p></div><div class="detail-links"><a href="https://fundf10.eastmoney.com/jbgk_${f.code}.html" target="_blank" rel="noopener">基金概况 ↗</a><a href="https://fundf10.eastmoney.com/ccmx_${f.code}.html" target="_blank" rel="noopener">持仓报告 ↗</a><a href="https://fundf10.eastmoney.com/jjfl_${f.code}.html" target="_blank" rel="noopener">完整费率 ↗</a><a href="https://fundf10.eastmoney.com/jjgg_${f.code}_1.html" target="_blank" rel="noopener">基金公告 ↗</a></div>`;
 if(!$('detail').open)$('detail').showModal();
}
async function loadData(){const r=await fetch('/api/data',{cache:'no-store'});if(!r.ok)throw Error('读取失败');dataset=await r.json();render()}
function message(s,error=false){$('status').textContent=s;$('status').classList.toggle('error',error)}
async function checkStatus(){try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error();const s=await r.json();$('refresh').disabled=s.running;$('refresh').querySelector('span').textContent=s.running?'正在刷新':'刷新数据';if(s.running){message(`${s.message} · ${s.done} / ${s.total||'…'} · ${s.errors} 项请求失败`);await loadData();timer=setTimeout(checkStatus,3000)}else{await loadData();message(`${s.message==='尚未刷新'?(dataset.message||'已读取上次快照'):s.message} · 额度数据 ${stamp(dataset.purchase_at)}。详情中的日期代表各自来源。`,s.errors>0||(!s.total&&dataset.error_count>0))}}catch{message('暂时无法连接网站数据服务，请稍后重试；已加载的数据仍可浏览。',true);$('refresh').disabled=false;$('refresh').querySelector('span').textContent='重试刷新'}}
$('refresh').onclick=async()=>{clearTimeout(timer);$('refresh').disabled=true;message('正在连接公开数据源…');try{const r=await fetch('/api/refresh',{method:'POST'});if(!r.ok)throw Error();timer=setTimeout(checkStatus,600)}catch{message('刷新未启动：暂时无法连接网站服务，请稍后重试。',true);$('refresh').disabled=false}};
document.querySelectorAll('[data-cat]').forEach(b=>b.onclick=()=>{category=b.dataset.cat;page=1;render()});document.querySelectorAll('[data-years]').forEach(b=>b.onclick=()=>{years=b.dataset.years;page=1;render()});['search','currency','channel','available','starred','minQuota','minReturn','maxFee','maxPremium'].forEach(id=>$(id).addEventListener('input',()=>{page=1;render()}));
document.querySelectorAll('[data-sort]').forEach(button=>button.onclick=()=>{const key=button.dataset.sort;if(key===sortKey)sortDirection=sortDirection==='asc'?'desc':'asc';else{sortKey=key;sortDirection=['return','quota'].includes(key)?'desc':'asc'}page=1;render()});
$('rows').onclick=e=>{const retry=e.target.closest('[data-retry]');if(retry){retryField(retry.dataset.code,retry.dataset.retry);return}const star=e.target.closest('[data-star]');if(star){const code=star.dataset.star;favorites.has(code)?favorites.delete(code):favorites.add(code);try{localStorage.setItem('fund-atlas-favorites',JSON.stringify([...favorites]))}catch{}render();return}const detail=e.target.closest('[data-detail]');if(detail)showDetail(detail.dataset.detail)};
$('detailContent').onclick=e=>{const retry=e.target.closest('[data-retry]');if(retry)retryField(retry.dataset.code,retry.dataset.retry)};
$('detail').addEventListener('close',()=>{detailCode=null});
$('prev').onclick=()=>{page--;render()};$('next').onclick=()=>{page++;render()};$('close').onclick=()=>$('detail').close();$('detail').onclick=e=>{if(e.target===$('detail')){const r=$('detail').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('detail').close()}};
function reset(){category='all';page=1;['search','minQuota','minReturn','maxFee','maxPremium'].forEach(id=>$(id).value='');$('currency').value='RMB';$('channel').value='all';$('available').checked=false;$('starred').checked=false;sortKey='return';sortDirection='desc';render()}$('reset').onclick=reset;$('emptyReset').onclick=reset;
$('export').onclick=()=>{const a=document.createElement('a');a.href='/api/export?'+new URLSearchParams({codes:filtered.map(f=>f.code).join(','),years});a.download='fund-atlas.csv';a.click()};
loadData().then(checkStatus).catch(async()=>{try{const r=await fetch('data.json');if(!r.ok)throw Error();dataset=await r.json();render();message('当前为只读快照，刷新服务暂不可用，请稍后重试。',true)}catch{message('未能加载网站数据，请检查网络后重新加载页面。',true)}});
