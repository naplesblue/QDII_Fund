/* One-fund historical unit NAV, read only from the site's shared history cache. */
(()=>{
 const panel=document.createElement('section');panel.className='nav-popover';panel.hidden=true;
 panel.setAttribute('role','dialog');panel.setAttribute('aria-label','历史单位净值');document.body.append(panel);
 const cache=new Map();let anchor=null,code='',range='3y',pinned=false,openTimer,closeTimer;
 const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const percent=n=>Number.isFinite(n)?`${n>0?'+':''}${n.toFixed(2)}%`:'未披露';
 function position(){if(!anchor)return;const r=anchor.getBoundingClientRect();panel.style.left=Math.max(8,Math.min(r.left,innerWidth-panel.offsetWidth-8))+'px';panel.style.top=Math.max(8,Math.min(r.bottom+8,innerHeight-panel.offsetHeight-8))+'px';}
 function close(){clearTimeout(openTimer);clearTimeout(closeTimer);panel.hidden=true;pinned=false;anchor=null;}
 async function read(fund,period){const key=fund+':'+period,old=cache.get(key);if(old&&Date.now()-old.loaded<60000)return old.data;
  const query=period==='30d'?'days=30':`years=${period.slice(0,-1)}`;
  const response=await fetch(`/api/nav-history?code=${fund}&${query}`,{cache:'no-store'});if(!response.ok)throw Error('历史读取失败');
  const data=await response.json();cache.set(key,{data,loaded:Date.now()});return data;
 }
 function controls(period){return `<div class="nav-periods" role="group" aria-label="净值区间">${[['30d','30 天'],['1y','1 年'],['3y','3 年'],['5y','5 年']].map(([key,label])=>`<button type="button" data-nav-range="${key}" aria-pressed="${key===period}">${label}</button>`).join('')}</div>`;}
 function inspect(p){return `<strong>${escape(p[0])}</strong><span>单位净值 <b>${Number(p[1]).toFixed(4)}</b></span><span>来源日涨跌 <b>${percent(p[2])}</b></span>${p[3]?`<em>分红 / 拆分标记：${escape(p[3])}</em>`:''}`;}
 function draw(target,raw,large){
  const points=raw.filter(p=>Array.isArray(p)&&/^\d{4}-\d{2}-\d{2}$/.test(p[0])&&Number.isFinite(Number(p[1]))&&Number(p[1])>0).map(p=>[p[0],Number(p[1]),p[2]==null?null:Number(p[2]),String(p[3]||'')]);
  if(!points.length){target.textContent='所选区间暂无逐日净值。历史来源缓存刷新后可再查看。';return;}
  const w=large?680:440,h=large?250:190,l=large?56:48,r=14,top=17,bottom=34;
  const dates=points.map(p=>Date.parse(p[0]+'T00:00:00+08:00')),values=points.map(p=>p[1]);
  const lo=Math.min(...values),hi=Math.max(...values),pad=Math.max((hi-lo)*.07,hi*.005,.0001),min=lo-pad,max=hi+pad;
  const x=i=>l+(dates[i]-dates[0])/(dates.at(-1)-dates[0]||1)*(w-l-r),y=v=>top+(max-v)/(max-min)*(h-top-bottom);
  let paths='',segment='';for(let i=0;i<points.length;i++){
   if(i&&dates[i]-dates[i-1]>14*86400000){if(segment)paths+=`<path d="${segment}"/>`;segment='';}
   segment+=`${segment?' L':'M'}${x(i).toFixed(1)},${y(values[i]).toFixed(1)}`;
  }if(segment)paths+=`<path d="${segment}"/>`;
  const grid=[min,(min+max)/2,max].map(v=>`<line x1="${l}" x2="${w-r}" y1="${y(v)}" y2="${y(v)}"/><text x="2" y="${y(v)+4}">${v.toFixed(4)}</text>`).join('');
  const events=points.map((p,i)=>p[3]?`<circle cx="${x(i)}" cy="${y(p[1])}" r="4"><title>${escape(p[0]+' · '+p[3])}</title></circle>`:'').join('');
  const isolated=points.map((p,i)=>((i===0||dates[i]-dates[i-1]>14*86400000)&&(i===points.length-1||dates[i+1]-dates[i]>14*86400000))?`<circle cx="${x(i)}" cy="${y(p[1])}" r="2.7"/>`:'').join('');
  target.innerHTML=`<div class="nav-inspect" aria-live="polite">${inspect(points.at(-1))}</div><svg class="nav-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="单位净值逐日折线图；悬停显示日期和净值十字线；长于十四天的缺口不连线">${grid}<g class="nav-line">${paths}</g><g class="nav-isolated">${isolated}</g><g class="nav-events">${events}</g><line class="nav-cross nav-cross-vertical" y1="${top}" y2="${h-bottom}" hidden/><line class="nav-cross nav-cross-horizontal" x1="${l}" x2="${w-r}" hidden/><circle class="nav-focus" r="5" hidden/><g class="nav-cross-labels" hidden><rect class="nav-date-badge" y="${h-29}" width="88" height="21" rx="4"/><text class="nav-date-label" y="${h-14}" text-anchor="middle"/><rect class="nav-value-badge" x="1" width="${l-5}" height="20" rx="4"/><text class="nav-value-label" x="${(l-3)/2}" text-anchor="middle"/></g><text x="${l}" y="${h-6}">${points[0][0]}</text><text x="${w-r}" y="${h-6}" text-anchor="end">${points.at(-1)[0]}</text></svg><p class="nav-sample">${points.length} 个估值日${points.length===1?' · 仅一个样本，尚不能形成曲线':''} · 橙点表示来源标记的分红 / 拆分</p>`;
  const svg=target.querySelector('svg'),vertical=svg.querySelector('.nav-cross-vertical'),horizontal=svg.querySelector('.nav-cross-horizontal'),focus=svg.querySelector('.nav-focus'),labels=svg.querySelector('.nav-cross-labels'),label=target.querySelector('.nav-inspect');
  svg.addEventListener('pointermove',event=>{const box=svg.getBoundingClientRect(),coord=(event.clientX-box.left)/box.width*w,at=dates[0]+Math.max(0,Math.min(1,(coord-l)/(w-l-r)))*(dates.at(-1)-dates[0]);
   let left=0,right=dates.length-1;while(left<right){const mid=Math.floor((left+right)/2);if(dates[mid]<at)left=mid+1;else right=mid;}
   const i=left>0&&Math.abs(dates[left-1]-at)<Math.abs(dates[left]-at)?left-1:left;
   const px=x(i),py=y(values[i]),dateX=Math.max(l+44,Math.min(w-r-44,px)),valueY=Math.max(top+10,Math.min(h-bottom-10,py));
   vertical.setAttribute('x1',px);vertical.setAttribute('x2',px);vertical.removeAttribute('hidden');
   horizontal.setAttribute('y1',py);horizontal.setAttribute('y2',py);horizontal.removeAttribute('hidden');
   focus.setAttribute('cx',px);focus.setAttribute('cy',py);focus.removeAttribute('hidden');
   labels.querySelector('.nav-date-badge').setAttribute('x',dateX-44);
   labels.querySelector('.nav-date-label').setAttribute('x',dateX);labels.querySelector('.nav-date-label').textContent=points[i][0];
   labels.querySelector('.nav-value-badge').setAttribute('y',valueY-10);
   labels.querySelector('.nav-value-label').setAttribute('y',valueY+4);labels.querySelector('.nav-value-label').textContent=values[i].toFixed(4);
   labels.removeAttribute('hidden');label.innerHTML=inspect(points[i]);
  });
 }
 async function fill(target,fund,period,large){const token=String(Number(target.dataset.request||0)+1);target.dataset.request=token;target.textContent='正在读取历史净值…';
  try{const data=await read(fund,period);if(!target.isConnected||target.dataset.request!==token)return;
   if(!data.points?.length){target.textContent=data.reason||'所选区间暂无有效历史净值。';return;}
   draw(target,data.points,large);target.insertAdjacentHTML('beforeend',`<p class="nav-basis">${escape(data.basis||'单位净值')} · 历史截止 ${escape(data.as_of||'未知')}；单位净值遇分红 / 拆分会跳变，不代表实际亏损或总回报。</p>`);
  }catch{if(target.isConnected)target.innerHTML='历史读取失败。<button type="button" data-nav-retry>重新读取</button>';}
 }
 function renderPanel(){panel.innerHTML=`<div class="nav-popover-head"><strong>${code} · 历史单位净值</strong><button type="button" data-nav-close aria-label="关闭净值历史">×</button></div>${controls(range)}<div class="nav-chart-body"></div><p class="nav-help">悬停图线查看估值日和来源日涨跌。点击净值可固定小窗。</p>`;panel.hidden=false;position();fill(panel.querySelector('.nav-chart-body'),code,range,false).finally(position);}
 function open(button,pin=false){clearTimeout(openTimer);clearTimeout(closeTimer);anchor=button;const host=button.closest('dialog')||document.body;if(panel.parentNode!==host)host.append(panel);code=button.dataset.navHistory;pinned=pin;renderPanel();}
 function mountDetail(fund,period){const section=document.querySelector(`[data-nav-detail="${fund}"]`);if(!section)return;
  const selected=/^(30d|[135]y)$/.test(String(period))?String(period):`${period}y`;
  section.innerHTML=`<div class="nav-history-head"><h3>历史单位净值</h3><span>估值日 · 非实时行情</span></div>${controls(selected)}<div class="nav-detail-body"></div>`;
  fill(section.querySelector('.nav-detail-body'),fund,selected,true);
 }
 document.addEventListener('mouseover',e=>{const button=e.target.closest('[data-nav-history]');if(!button||pinned||button.contains(e.relatedTarget))return;clearTimeout(openTimer);openTimer=setTimeout(()=>open(button),300);});
 document.addEventListener('mouseout',e=>{if(!e.target.closest('[data-nav-history]'))return;clearTimeout(openTimer);if(!pinned)closeTimer=setTimeout(close,250);});
 panel.addEventListener('mouseenter',()=>clearTimeout(closeTimer));panel.addEventListener('mouseleave',()=>{if(!pinned)closeTimer=setTimeout(close,250);});
 document.addEventListener('click',e=>{const button=e.target.closest('[data-nav-history]');if(button){open(button,true);return;}if(!e.composedPath().includes(panel))close();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)close();});
 panel.addEventListener('click',e=>{if(e.target.closest('[data-nav-close]')){close();return;}const period=e.target.closest('[data-nav-range]');if(period){range=period.dataset.navRange;pinned=true;renderPanel();}if(e.target.closest('[data-nav-retry]'))renderPanel();});
 document.addEventListener('click',e=>{const period=e.target.closest('[data-nav-detail] [data-nav-range]');if(period)mountDetail(period.closest('[data-nav-detail]').dataset.navDetail,period.dataset.navRange);const retry=e.target.closest('[data-nav-detail] [data-nav-retry]');if(retry)mountDetail(retry.closest('[data-nav-detail]').dataset.navDetail,retry.closest('[data-nav-detail]').querySelector('[aria-pressed=true]').dataset.navRange);});
 window.addEventListener('resize',position);window.addEventListener('scroll',()=>{if(!panel.hidden)position();},true);
 window.NavHistory={mountDetail};
})();
