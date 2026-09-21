/* Capabilities, daily status and sortable amount are intentionally independent. */
(function(root){
 function amount(f){
  if(!['otc','both'].includes(f.channel)||!['开放申购','限大额'].includes(f.purchase_status))return null;
  if(['error','loading','missing','na'].includes(f.field_states?.quota?.status))return null;
  return Number.isFinite(f.quota)&&f.quota>0&&['RMB','USD'].includes(f.currency)?f.quota:null;
 }
 function info(f){
  const channel=f.channel||'unknown',state=f.field_states?.quota?.status;
  let otc='待核验',tone='muted',retry=false;
  if(channel==='exchange')otc='不适用';
  else if(['otc','both'].includes(channel)){
   if(['error','loading','missing'].includes(state)){otc=state==='loading'?'获取中':'待核验';retry=true;}
   else if(f.purchase_status==='暂停申购'){otc='暂停';tone='paused';}
   else if(amount(f)!==null){otc=(f.currency==='USD'?'US$':'¥')+amount(f).toLocaleString('zh-CN')+'/日';tone='normal';}
   else {otc='待核验';retry=true;}
  }
  return {otc,tone,retry,primary:channel==='otc'?'不适用':'待核验',trading:['exchange','both'].includes(channel)?'已上市':channel==='otc'?'未上市':'待核验'};
 }
 function compare(a,b,direction){
  const av=amount(a),bv=amount(b);
  if(av===null)return bv===null?a.code.localeCompare(b.code):1;
  if(bv===null)return -1;
  // Currency groups remain stable in either sort direction; no FX conversion implied.
  if(a.currency!==b.currency)return a.currency==='RMB'?-1:1;
  return (direction==='desc'?bv-av:av-bv)||a.code.localeCompare(b.code);
 }
 const api={amount,info,compare};root.TradeInfo=api;
 if(typeof module!=='undefined')module.exports=api;
})(globalThis);
