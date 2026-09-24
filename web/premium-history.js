/* On-demand history: opening the chart never requests upstream quotes. */
(()=>{
 const panel=document.createElement('section');panel.className='premium-popover';panel.hidden=true;
 panel.setAttribute('role','dialog');panel.setAttribute('aria-label','场内溢价历史');document.body.append(panel);
 let anchor=null,code='',days=30,pinned=false,openTimer,closeTimer,request=0;
 const cache=new Map(),fmt=n=>`${n>0?'+':''}${n.toFixed(2)}%`;
 const date=t=>new Date(t*1000).toLocaleString('zh-CN',{hour12:false});
 function position(){if(!anchor)return;const r=anchor.getBoundingClientRect();panel.style.left=Math.max(8,Math.min(r.right-420,innerWidth-panel.offsetWidth-8))+'px';panel.style.top=Math.max(8,Math.min(r.bottom+8,innerHeight-panel.offsetHeight-8))+'px';}
 function close(){clearTimeout(openTimer);clearTimeout(closeTimer);request++;panel.hidden=true;pinned=false;anchor=null;}
 function chart(points){
  const w=380,h=150,l=46,r=10,top=12,bottom=25;
  const values=points.map(p=>p.premium),low=Math.min(0,...values),high=Math.max(0,...values),pad=Math.max(.1,(high-low)*.08),min=low-pad,max=high+pad;
  const first=points[0].time,last=points.at(-1).time;
  const x=t=>l+(t-first)/(last-first||1)*(w-l-r),y=v=>top+(max-v)/(max-min)*(h-top-bottom);
  let lines='',previous=null;
  for(const p of points){if(previous&&p.time-previous.time<=1200)lines+=`<path d="M${x(previous.time)},${y(previous.premium)} L${x(p.time)},${y(p.premium)}"/>`;previous=p;}
  const grid=[min,0,max].map(v=>`<line x1="${l}" x2="${w-r}" y1="${y(v)}" y2="${y(v)}" stroke="#dce3dc" stroke-dasharray="3 3"/><text x="2" y="${y(v)+4}">${fmt(v)}</text>`).join('');
  const dots=points.map(p=>`<circle cx="${x(p.time)}" cy="${y(p.premium)}" r="2"><title>${date(p.time)} · ${fmt(p.premium)}</title></circle>`).join('');
  return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="IOPV 折溢价采样曲线，长时间缺口不连线">${grid}<g stroke="#23654d" stroke-width="1.5" fill="none">${lines}</g><g fill="#23654d">${dots}</g><text x="${l}" y="${h-4}">${new Date(first*1000).toLocaleDateString('zh-CN')}</text><text x="${w-r}" y="${h-4}" text-anchor="end">${new Date(last*1000).toLocaleDateString('zh-CN')}</text></svg>`;
 }
 async function render(){
  const token=++request;
  panel.innerHTML=`<div class="premium-popover-head"><strong>${code} · 场内溢价历史</strong><button type="button" data-history-close aria-label="关闭溢价历史">×</button></div><div class="history-periods">${[7,30,90].map(n=>`<button type="button" data-history-days="${n}" aria-pressed="${n===days}">近 ${n} 天</button>`).join('')}</div><div class="history-content" aria-live="polite">正在读取采样记录…</div><p class="history-help">价格 / IOPV − 1 · 数据可能延迟<br>交易时段约每 5 分钟采样；中断处不连线。点击溢价数字可固定小窗。</p>`;
  panel.hidden=false;position();
  try{
   const key=code+':'+days;let data=cache.get(key);
   if(!data||Date.now()-data.loaded>60000){const response=await fetch(`/api/premium-history?code=${code}&days=${days}`,{cache:'no-store'});if(!response.ok)throw Error();data={...await response.json(),loaded:Date.now()};cache.set(key,data);}
   if(token!==request)return;
   const points=data.points.filter(p=>Number.isFinite(p.premium)&&Number.isFinite(p.time));
   const box=panel.querySelector('.history-content');
   if(!points.length)box.textContent='所选区间暂无有效采样。历史从启用后积累，不补造过去的数据。';
   else{
    const values=points.map(p=>p.premium),last=points.at(-1);
    box.innerHTML=`<div class="history-stats"><span>最后采样 <b>${fmt(last.premium)}</b></span><span>最高 <b>${fmt(Math.max(...values))}</b></span><span>最低 <b>${fmt(Math.min(...values))}</b></span></div>${chart(points)}<p class="history-time">${points.length} 个有效样本 · 最后行情 ${date(last.time)}${points.length===1?' · 仅一个样本，尚不能形成曲线':''}</p>`;
   }
   position();
  }catch{if(token===request){panel.querySelector('.history-content').innerHTML='历史读取失败。<button type="button" data-history-retry>重新读取</button>';position();}}
 }
 function open(button,pin=false){clearTimeout(closeTimer);clearTimeout(openTimer);anchor=button;const host=button.closest('dialog')||document.body;if(panel.parentNode!==host)host.append(panel);code=button.dataset.premiumHistory;pinned=pin;render();}
 document.addEventListener('mouseover',e=>{const button=e.target.closest('[data-premium-history]');if(!button||pinned||button.contains(e.relatedTarget))return;clearTimeout(openTimer);openTimer=setTimeout(()=>open(button),300);});
 document.addEventListener('mouseout',e=>{if(!e.target.closest('[data-premium-history]'))return;clearTimeout(openTimer);if(!pinned)closeTimer=setTimeout(close,250);});
 panel.addEventListener('mouseenter',()=>clearTimeout(closeTimer));
 panel.addEventListener('mouseleave',()=>{if(!pinned)closeTimer=setTimeout(close,250);});
 document.addEventListener('click',e=>{const button=e.target.closest('[data-premium-history]');if(button){open(button,true);return;}if(!e.composedPath().includes(panel))close();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden){const previous=anchor;close();previous?.focus();}});
 panel.addEventListener('click',e=>{if(e.target.closest('[data-history-close]')){close();return;}const period=e.target.closest('[data-history-days]');if(period){days=Number(period.dataset.historyDays);pinned=true;render();}if(e.target.closest('[data-history-retry]'))render();});
 window.addEventListener('resize',position);window.addEventListener('scroll',()=>{if(!panel.hidden)position();},true);
})();
