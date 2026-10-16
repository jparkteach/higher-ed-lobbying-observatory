'use strict';
const $=id=>document.getElementById(id), esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors={Public:'#176c70',Private:'#81719d','For-profit':'#c5693a'}, sectorLabel=s=>s==='Private'?'Private nonprofit':s;
const fmt=new Intl.NumberFormat('en-US',{maximumFractionDigits:0}), n=x=>fmt.format(x), pct=x=>Number.isFinite(x)?x.toFixed(1)+'%':'Unavailable';
const money=x=>!Number.isFinite(x)?'Unavailable':(x<0?'−':'')+'$'+n(Math.abs(x));
const short=x=>!Number.isFinite(x)?'—':(x<0?'−':'')+'$'+(Math.abs(x)>=1e6?(Math.abs(x)/1e6).toFixed(1)+'m':Math.abs(x)>=1e3?(Math.abs(x)/1e3).toFixed(0)+'k':n(Math.abs(x)));
const mean=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
const finite=x=>x!==null&&Number.isFinite(x);
const flags=['landgrant','hbcu','doctoral','aau','hospital','medical','hsi','tribal','msi'];
let DATA,ROWS,CROSS=[],CURRENT=[],FILTERED=[];
function svg(w,h,content,label){return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}">${content}</svg>`}
function txt(x,y,text,cls='',anchor='start'){return `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${esc(text)}</text>`}
function line(x1,y1,x2,y2,attrs='class="grid"'){return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${attrs}/>`}
function table(headers,rows){return `<table><thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr${r.entity?` data-entity="${esc(r.entity)}" tabindex="0" role="button" aria-label="Inspect ${esc(r[0])}"`:''}>${r.map(c=>`<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`}
function empty(id,message){$(id).innerHTML=`<div class="empty">${esc(message)}</div>`}
function crossSection(rows){
  const groups=new Map(); for(const r of rows){if(!groups.has(r.entity))groups.set(r.entity,[]);groups.get(r.entity).push(r)}
  return [...groups].map(([entity,g])=>{
    g.sort((a,b)=>a.year-b.year);const valid=g.filter(r=>r.budget>0),sum=(a,k)=>a.reduce((s,r)=>s+(r[k]??0),0);
    const counts={};g.forEach(r=>counts[r.sector]=(counts[r.sector]||0)+1);const max=Math.max(...Object.values(counts));
    const sector=[...g].reverse().find(r=>counts[r.sector]===max).sector;
    let r={entity,name:g.at(-1).name,kind:g.at(-1).kind,sector,years:g.length,lobbied:Math.max(...g.map(r=>r.lobbied)),
      spend:mean(g.map(r=>r.spend_real)),budget:valid.length?mean(valid.map(r=>r.budget_real)):null,
      rd:valid.length?100*sum(valid,'rd_real')/sum(valid,'budget_real'):null,
      pell_pct:valid.length?100*sum(valid,'pell_real')/sum(valid,'budget_real'):null,
      imputed_spend:sum(g,'imputed_spend'),nominal:sum(g,'spend'),fteug:mean(g.map(r=>r.fteug))};
    flags.forEach(f=>r[f]=Math.max(...g.map(r=>r[f])));return r;
  });
}
function selection(){
  let start=+$('start').value,end=+$('end').value;if(start>end){end=start;$('end').value=String(end)}
  const sector=$('sector').value,kind=$('kind').value;
  FILTERED=ROWS.filter(r=>(sector==='All'||r.sector===sector)&&(kind==='All'||r.kind===kind));
  CURRENT=FILTERED.filter(r=>r.year>=start&&r.year<=end&&r.lobbied!==null);
  CROSS=crossSection(CURRENT);
  $('filter-context').textContent=`${n(CROSS.length)} standalone institutions and systems · ${n(CURRENT.length)} entity-years · ${start}–${end}. Sector filters apply to annual records; charts 1–4 update together. Models below use their labeled full sample.`;
  const sum=k=>CURRENT.reduce((a,r)=>a+(r[k]??0),0),ever=CROSS.filter(r=>r.lobbied===1).length;
  $('kpis').innerHTML=[
    [short(sum('spend_real')),'Total lobbying spending','In constant 2022 dollars'],
    [pct(CROSS.length?100*ever/CROSS.length:NaN),'Ever lobbied in this window',`${n(ever)} of ${n(CROSS.length)} entities`],
    [n(CROSS.length),'Institutions & systems',`${n(CROSS.filter(r=>r.kind==='Standalone').length)} standalone · ${n(CROSS.filter(r=>r.kind==='System').length)} systems`],
    [pct(sum('spend')?100*sum('imputed_spend')/sum('spend'):NaN),'Spending allocated to campuses','Recombined into system totals here']
  ].map(([a,b,c])=>`<div class="kpi"><strong>${a}</strong><span>${b}</span><small>${c}</small></div>`).join('');
  trend();profile();scatter('pell');scatter('rd');directory();
}
function trend(){
  const metric=$('trend-metric').value,start=+$('start').value,end=+$('end').value;
  const years=Array.from({length:2024-start+1},(_,i)=>start+i),sectors=Object.keys(colors).filter(s=>$('sector').value==='All'||$('sector').value===s),items=[];
  for(const year of years)for(const sector of sectors){
    const z=FILTERED.filter(r=>r.year===year&&r.sector===sector),observed=year<=end&&year<=2022;
    if(year>2022)items.push({year,sector,value:null,entities:z.length,pending:true});
    else if(observed){const spends=z.reduce((a,r)=>a+(metric==='nominal'?r.spend:r.spend_real),0),rate=z.length?100*z.reduce((a,r)=>a+r.lobbied,0)/z.length:null;items.push({year,sector,value:metric==='rate'?rate:spends,entities:z.length})}
    else items.push({year,sector,value:null,entities:0,outside:true});
  }
  const W=650,H=345,L=65,R=18,T=25,B=47,plotW=W-L-R,plotH=H-T-B,x=y=>L+(y-start)/(2024-start)*plotW;
  const vals=items.map(r=>r.value).filter(finite),max=metric==='rate'?Math.max(10,Math.ceil(Math.max(0,...vals)/10)*10):Math.max(1,...vals)*1.1,y=v=>H-B-v/max*plotH;
  let s='';for(let i=0;i<=4;i++){const v=max*i/4;s+=line(L,y(v),W-R,y(v))+txt(L-9,y(v)+4,metric==='rate'?pct(v):short(v),'','end')}
  const pendingX=x(2022.5);s+=`<rect x="${pendingX}" y="${T}" width="${W-R-pendingX}" height="${plotH}" fill="#f5efe1"/>`+txt((pendingX+W-R)/2,17,'PENDING','','middle');
  for(const yr of years)s+=txt(x(yr),H-20,String(yr),'','middle');
  for(const sec of sectors){let p='';for(const a of items.filter(r=>r.sector===sec)){if(!finite(a.value)){p='';continue}if(p){s+=line(p[0],p[1],x(a.year),y(a.value),`stroke="${colors[sec]}" stroke-width="2.5"`)}p=[x(a.year),y(a.value)];const tip=`${sectorLabel(sec)} · ${a.year}\n${metric==='rate'?pct(a.value):money(a.value)}\n${n(a.entities)} entities`;
      s+=`<circle cx="${x(a.year)}" cy="${y(a.value)}" r="4" fill="${colors[sec]}" data-tip="${esc(tip)}"><title>${esc(tip)}</title></circle>`;
    }}
  for(const yr of [2023,2024])s+=txt(x(yr),T+plotH/2,'—','','middle');
  $('trend-chart').innerHTML=svg(W,H,s,'Annual lobbying spending or participation by sector; 2023 and 2024 are pending.');
  $('sector-legend').innerHTML=sectors.map(sec=>`<span><i style="background:${colors[sec]}"></i>${esc(sectorLabel(sec))}</span>`).join('');
  $('trend-table').innerHTML=table(['Year','Sector',metric==='rate'?'Annual participation':'Spending','Entities'],items.filter(r=>!r.outside).map(r=>[r.year,sectorLabel(r.sector),r.pending?'Pending':metric==='rate'?pct(r.value):money(r.value),n(r.entities)]));
}
function profile(){
  const groups=[['doctoral','Doctoral'],['aau','AAU member'],['hospital','Hospital'],['medical','Medical program'],['landgrant','Land grant'],['hbcu','HBCU'],['msi','Minority serving']];
  const W=650,H=345,L=160,R=55,T=30,B=35,pw=W-L-R,step=37,rows=[];let s='';
  for(let i=0;i<=4;i++){const x=L+pw*i/4;s+=line(x,T-8,x,H-B)+txt(x,H-12,(i*25)+'%','','middle')}
  groups.forEach(([f,label],i)=>{const y=T+i*step;s+=txt(L-12,y+13,label,'strong','end');
    [1,0].forEach((value,j)=>{const z=CROSS.filter(r=>r[f]===value),count=z.filter(r=>r.lobbied===1).length,rate=z.length?100*count/z.length:null;rows.push([label,value?'Yes':'No',n(z.length),n(count),pct(rate)]);
      if(rate!==null){const tip=`${label}: ${value?'Yes':'No'}\n${count} of ${z.length} ever lobbied (${pct(rate)})`;
      s+=`<rect x="${L}" y="${y+j*12}" height="9" width="${pw*rate/100}" rx="2" fill="${j?'#c9d4d2':'#176c70'}" data-tip="${esc(tip)}"><title>${esc(tip)}</title></rect>`;}
    });
  });
  if(!CROSS.length){empty('profile-chart','No institutions match these filters.');return}
  $('profile-chart').innerHTML=svg(W,H,s,'Unadjusted shares ever lobbying among institutions with and without seven characteristics.');
  $('profile-table').innerHTML=table(['Characteristic','Has it?','Entities','Ever lobbied','Share'],rows);
}
function scatter(which){
  const term=which==='pell'?'pell_pct':'rd',sectorFilter=r=>which==='pell'?r.sector==='For-profit':r.sector!=='For-profit';
  const cohort=CROSS.filter(sectorFilter),valid=cohort.filter(r=>finite(r[term])),limited=$('ratio-limit').checked,z=valid.filter(r=>!limited||r[term]<=100),omitted=valid.length-z.length;
  const model=DATA.models.find(r=>r.spec===(which==='pell'?'H1 For-profit':'H2 Nonprofit')&&r.outcome==='ols'&&r.term===(which==='pell'?'pell10':'rd10'));
  if(!z.length){empty(which+'-chart','No eligible institutions with valid funding ratios in this selection.');$(which+'-stat').textContent=`${cohort.length} eligible entities · ${cohort.length-valid.length} missing valid budgets`;$(which+'-table').innerHTML='';return}
  const W=650,H=335,L=65,R=20,T=20,B=53,pw=W-L-R,ph=H-T-B,xmax=Math.max(1,...z.map(r=>r[term]))*1.06,ymax=Math.max(Math.log1p(1000),...z.map(r=>Math.log1p(r.spend)))*1.05;
  const x=v=>L+v/xmax*pw,y=v=>H-B-Math.log1p(v)/ymax*ph;let s='';
  const ticks=[0,1000,10000,100000,1000000,10000000].filter(v=>Math.log1p(v)<=ymax);
  for(const v of ticks)s+=line(L,y(v),W-R,y(v))+txt(L-9,y(v)+4,short(v),'','end');
  for(let i=0;i<=4;i++){const v=xmax*i/4;s+=txt(x(v),H-B+23,v.toFixed(xmax<10?1:0)+'%','','middle')}
  s+=txt(L+pw/2,H-4,(which==='pell'?'Pell':'Federal R&D')+' / budget (%)','axis-label','middle');
  const sorted=[...z].sort((a,b)=>a.spend-b.spend);
  for(const r of sorted){const tip=`${r.name}\n${sectorLabel(r.sector)} · ${r.kind}\n${pct(r[term])} funding dependence\n${money(r.spend)} average annual lobbying\n${r.years} observed years · click for records`;
    s+=`<circle cx="${x(r[term])}" cy="${y(r.spend)}" r="${r.kind==='System'?4.7:3.7}" fill="${colors[r.sector]}" fill-opacity=".60" stroke="white" stroke-width=".5" data-entity="${esc(r.entity)}" data-tip="${esc(tip)}"><title>${esc(tip)}</title></circle>`;
  }
  $(which+'-chart').innerHTML=svg(W,H,s,`${which==='pell'?'For-profit Pell':'Nonprofit research'} funding dependence versus average annual lobbying spending. Click points or use chart data.`);
  const xm=mean(z.map(r=>r[term])),ym=mean(z.map(r=>r.spend));let xy=0,xx=0,yy=0;for(const r of z){xy+=(r[term]-xm)*(r.spend-ym);xx+=(r[term]-xm)**2;yy+=(r.spend-ym)**2}const corr=xx&&yy?xy/Math.sqrt(xx*yy):null;
  $(which+'-stat').textContent=`${n(z.length)} points · Pearson r (unlogged spending): ${corr===null?'unavailable':corr.toFixed(2)} · ${n(cohort.length-valid.length)} missing budgets${omitted?' · '+omitted+' above 100% omitted':''}`;
  $(which+'-table').innerHTML=table(['Institution','Type','Funding / budget','Avg. annual lobbying','Observed years'],sorted.reverse().map(r=>Object.assign([r.name,r.kind,pct(r[term]),money(r.spend),r.years],{entity:r.entity})));
}
function models(){
  const spec=$('model-spec').value,outcome=$('model-outcome').value,diag=DATA.diagnostics.find(r=>r.spec===spec&&r.outcome===outcome);
  const all=DATA.models.filter(r=>r.spec===spec&&r.outcome===outcome),z=all.filter(r=>r.term!=='const'&&!r.term.startsWith('year_'));
  if(!z.length){empty('model-chart',diag?.reason||'This specification is unavailable.');$('model-meta').textContent='';$('model-reading').textContent='';$('model-table').innerHTML='';return}
  const W=800,L=285,R=30,T=30,step=31,H=T+z.length*step+46,pw=W-L-R,log=outcome==='logit';
  const transform=v=>log?Math.log(v):v,lo=Math.min(log?0:0,...z.map(r=>transform(r.effect_lo))),hi=Math.max(log?0:0,...z.map(r=>transform(r.effect_hi))),pad=Math.max((hi-lo)*.05,log?.1:1),x=v=>L+(transform(v)-(lo-pad))/(hi-lo+2*pad)*pw;
  let s='';for(let i=0;i<=4;i++){const t=lo+(hi-lo)*i/4,v=log?Math.exp(t):t,xx=x(v);s+=line(xx,T-12,xx,H-44)+txt(xx,H-22,log?(v>=100?n(v):v<.01?v.toExponential(0):v.toFixed(2)):short(v),'','middle')}
  s+=line(x(log?1:0),T-15,x(log?1:0),H-44,'stroke="#778f89" stroke-dasharray="4 4"');
  z.forEach((r,i)=>{const y=T+i*step,c=r.p<.05?'#176c70':'#98a5a2',tip=`${r.label}\n${log?'Odds ratio':'Spending change'}: ${log?r.effect.toFixed(3):money(r.effect)}\n95% CI: ${log?r.effect_lo.toFixed(3):money(r.effect_lo)} to ${log?r.effect_hi.toFixed(3):money(r.effect_hi)}\np = ${r.p<.001?'<0.001':r.p.toFixed(3)}`;
    s+=txt(L-16,y+4,r.label.replace(' · +10 percentage points',' · +10 pp').replace(' · +$100 million (2022 dollars)',' · +$100m').replace(' · +1,000',' · +1,000'),'strong','end');
    s+=line(x(r.effect_lo),y,x(r.effect_hi),y,`stroke="${c}" stroke-width="2"`)+line(x(r.effect_lo),y-4,x(r.effect_lo),y+4,`stroke="${c}"`)+line(x(r.effect_hi),y-4,x(r.effect_hi),y+4,`stroke="${c}"`)+`<circle cx="${x(r.effect)}" cy="${y}" r="4.5" fill="${c}" data-tip="${esc(tip)}"><title>${esc(tip)}</title></circle>`;
  });
  $('model-chart').innerHTML=svg(W,H,s,'Adjusted coefficient estimates with 95 percent confidence intervals. Teal marks p below 0.05.');
  $('model-meta').textContent=`N = ${n(diag.n)} ${spec.startsWith('Panel')?'entity-years; '+n(diag.clusters)+' clusters':'entities'} · ${diag.covariance} uncertainty · ${log?'McFadden pseudo-R²':'R²'} = ${diag.fit.toFixed(3)}. Intervals are 95%; teal marks p < .05. Funding changes are +10 percentage points.${diag.dropped_collinear.length?' Collinear terms omitted: '+diag.dropped_collinear.join(', ')+'.':''}`;
  const focus=z.filter(r=>['rd10','pell10'].includes(r.term));
  $('model-reading').innerHTML=`<h4>${log?'The decision to lobby':'The amount spent'}</h4><p>${log?'An odds ratio above 1 indicates higher odds of lobbying; below 1 indicates lower odds. Odds are not probabilities.':'A coefficient above $0 indicates higher average annual lobbying spending, including zeros. Dollar coefficients are in 2022 dollars.'}</p>`+focus.map(r=>`<p><strong>${r.term==='rd10'?'Research dependence':'Pell dependence'}</strong><br>${log?r.effect.toFixed(2)+'× the odds':(r.effect<0?'−':'+')+money(Math.abs(r.effect))} for +10 percentage points.<br>95% CI: ${log?r.effect_lo.toFixed(2):money(r.effect_lo)} to ${log?r.effect_hi.toFixed(2):money(r.effect_hi)}.<br>${r.p<.05?'The interval excludes the null.':'The interval includes the null.'}</p>`).join('')+`<p>${spec.startsWith('Panel')?'Annual models add year indicators and cluster uncertainty by institution/system. They do not include institution fixed effects.':'Cross sections use one row per standalone or system, with an ever-lobbied outcome.'} These estimates describe conditional associations.</p>`;
  $('model-table').innerHTML=table(['Term',log?'Odds ratio':'Coefficient ($2022)','95% low','95% high','Robust p','Conventional SE'],all.map(r=>[r.label,log?r.effect.toFixed(4):money(r.effect),log?r.effect_lo.toFixed(4):money(r.effect_lo),log?r.effect_hi.toFixed(4):money(r.effect_hi),r.p<.0001?'<0.0001':r.p.toFixed(4),r.se_conventional.toFixed(4)]));
}
function directory(){
  const q=$('search').value.toLowerCase().trim(),z=CROSS.filter(r=>r.name.toLowerCase().includes(q)).sort((a,b)=>b.spend-a.spend),shown=z.slice(0,50);
  $('institution-table').innerHTML=table(['Institution / system','Sector','Type','Ever lobbied','Annual avg. ($2022)','Pell / budget','R&D / budget'],shown.map(r=>Object.assign([r.name,sectorLabel(r.sector),r.kind,r.lobbied?'Yes':'No',money(r.spend),pct(r.pell_pct),pct(r.rd)],{entity:r.entity})));
  $('directory-count').textContent=`Showing ${n(shown.length)} of ${n(z.length)} matching entities. Export selection for all rows.`;
}
function detail(entity){
  const g=ROWS.filter(r=>r.entity===entity).sort((a,b)=>a.year-b.year),r=CROSS.find(r=>r.entity===entity)||crossSection(g.filter(r=>r.lobbied!==null))[0];if(!g.length)return;
  $('detail-content').innerHTML=`<p class="eyebrow">INSTITUTION RECORD</p><h2>${esc(g.at(-1).name)}</h2><p>${esc(g.at(-1).kind)} · ${esc(sectorLabel(g.at(-1).sector))}</p><p class="note">Annual records below show the full supplied period, independent of filters. Spending is a system total when campuses belong to a system. Funding shares require a positive reported budget.</p><div class="data-table">`+table(['Year','Campuses','Lobbied','Nominal spend','Spend ($2022)','Pell / budget','R&D / budget','Allocated campuses','Missing campus budgets'],g.map(a=>[a.year,a.campuses,a.lobbied===null?'Pending':a.lobbied?'Yes':'No',money(a.spend),money(a.spend_real),pct(a.pell_pct),pct(a.rd),a.lobbied===null?'Pending':a.imputed_n,a.budget_missing_campuses]))+'</div>';
  $('detail').showModal();$('tooltip').hidden=true;
}
function download(){
  const cols=['entity','name','sector','kind','years','lobbied','spend','budget','pell_pct','rd','fteug',...flags],labels={entity:'source_reporting_group',years:'observed_years',lobbied:'ever_lobbied',spend:'mean_annual_lobbying_2022_dollars',budget:'mean_annual_budget_2022_dollars',rd:'federal_rd_dependence_pct',pell_pct:'pell_dependence_pct',fteug:'mean_fte_undergraduates'},quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"',content=[cols.map(c=>labels[c]||c).join(','),...CROSS.map(r=>cols.map(c=>quote(r[c])).join(','))].join('\r\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8'}));a.download=`lobbying-selection-${$('start').value}-${$('end').value}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),5000);
}
async function init(){
  try{const response=await fetch('data.json');if(!response.ok)throw Error('Data did not load');DATA=await response.json();ROWS=DATA.rows.map(row=>Object.fromEntries(DATA.columns.map((c,i)=>[c,row[i]])));
  for(const id of ['start','end'])$(id).innerHTML=DATA.audit.observed_years.map(y=>`<option value="${y}">${y}</option>`).join('');$('start').value='2015';$('end').value='2022';
  $('audit-note').textContent=`Audit: ${n(DATA.audit.source_rows)} campus-years; ${n(DATA.audit.source_campuses)} unique campuses; ${n(DATA.audit.observed_rows)} observed lobbying records; ${n(DATA.audit.pending_rows)} pending records. ${n(DATA.audit.invalid_campus_budgets_observed)} observed campus-years have nonpositive budgets. Main models exclude ${n(DATA.audit.cross_missing_finance)} entities without usable budget data. Source SHA-256: ${DATA.audit.sha256}.`;
  $('filters').addEventListener('submit',e=>e.preventDefault());['start','end','kind','sector'].forEach(id=>$(id).addEventListener('change',selection));$('trend-metric').addEventListener('change',trend);$('ratio-limit').addEventListener('change',()=>{scatter('pell');scatter('rd')});['model-spec','model-outcome'].forEach(id=>$(id).addEventListener('change',models));$('search').addEventListener('input',directory);$('download-selection').addEventListener('click',download);
  $('reset').addEventListener('click',()=>{$('start').value='2015';$('end').value='2022';$('kind').value='All';$('sector').value='All';$('search').value='';$('ratio-limit').checked=true;selection()});
  document.addEventListener('click',e=>{const t=e.target.closest('[data-target]');if(t){const el=$(t.dataset.target);el.hidden=!el.hidden;t.textContent=el.hidden?(el.id==='model-table'?'Show coefficients & confidence intervals':'Show chart data'):'Hide chart data';t.setAttribute('aria-expanded',String(!el.hidden))}const p=e.target.closest('[data-entity]');if(p)detail(p.dataset.entity)});
  document.addEventListener('keydown',e=>{const p=e.target.closest('[data-entity]');if(p&&['Enter',' '].includes(e.key)){e.preventDefault();detail(p.dataset.entity)}});
  document.addEventListener('pointermove',e=>{const t=e.target.closest('[data-tip]');if(!t){$('tooltip').hidden=true;return}$('tooltip').textContent=t.dataset.tip;$('tooltip').hidden=false;$('tooltip').style.left=Math.max(8,Math.min(innerWidth-310,e.clientX+13))+'px';$('tooltip').style.top=Math.max(8,Math.min(innerHeight-$('tooltip').offsetHeight-10,e.clientY+12))+'px'});
  $('close-detail').addEventListener('click',()=>$('detail').close());$('detail').addEventListener('click',e=>{if(e.target===$('detail')){const b=$('detail').getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)$('detail').close()}});
  selection();models();window.observatory={getData:()=>DATA,getSelection:()=>CROSS};
  }catch(err){$('error').hidden=false;$('error').textContent='The analysis could not load. '+err.message;$('filter-context').textContent='Data unavailable.';console.error(err)}
}
init();
