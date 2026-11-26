'use strict';
const $ = id => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const API_BASE = String(window.KATUP_CONFIG?.apiBase || '').replace(/\/+$/, '');
const state = {telemetry: {}, comparison: {}, case: {}, network: null};
const modeLabels={baseline:'Tanpa KATUP',katup:'KATUP Heuristik',hybrid:'KATUP Hybrid'};
let mapRevision='',mapRequest=0;
let stream, retryTimer, lastSeriesTime = -1, lastComparison = '', lastEvents = '';
let frames = [], lastFrameReceived = 0, packetInterval = 250, currentRun = null;
const vehicleNodes = new Map();
const views = {corridor: [-340,-205,1020,390], bottleneck:[140,-85,290,170], junction:[-130,-110,450,220], detail:[180,-32,115,64], all:[-580,-355,1460,710]};
let view = [...views.corridor];
const palette = ['#cbdde9','#84b8ed','#f1d68d','#dda3ab','#b8c1cf','#a6d6d0'];
function apiUrl(path){return API_BASE ? `${API_BASE}${path.startsWith('/')?path:`/${path}`}` : path;}
function apiFetch(path, options={}){return fetch(apiUrl(path), {...options, credentials:'include'});}
function socketUrl(path){const base=new URL(API_BASE||location.origin, location.href);base.protocol=base.protocol==='https:'?'wss':base.protocol==='http:'?'ws':base.protocol;base.pathname=path;base.search='';base.hash='';return base.toString();}
function svgEl(tag, attrs={}) {const e=document.createElementNS(NS,tag); for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;}
function setText(id, value){const e=$(id);if(e&&e.textContent!==String(value))e.textContent=value;}
function fmt(v,d=0){return v===undefined||v===null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d);}
function statusClass(el,status){el.textContent=status;el.className='status-chip '+(['ACTIVE','ADAPTIVE','KATUP_ACTIVE','SIAP'].includes(status)?'active':status==='RISIKO'?'warn':'');}
function polyline(points, cls, width){return svgEl('polyline',{points:points.map(([x,y])=>`${x},${-y}`).join(' '),class:cls,'stroke-width':width});}
function bounds(points,pad=80){const xs=points.map(p=>p[0]),ys=points.map(p=>-p[1]);const x=Math.min(...xs)-pad,y=Math.min(...ys)-pad,w=Math.max(120,Math.max(...xs)-x+pad),h=Math.max(90,Math.max(...ys)-y+pad);return [x,y,w,h];}
function label(x,y,name,extra={}){const t=svgEl('text',{x,y,class:'road-label',...extra});t.textContent=name;$('labels').append(t);}
async function buildMap(){
  const revision=++mapRequest;
  $('map').setAttribute('aria-busy','true');
  try{
  const query=new URLSearchParams({corridor:$('corridor').value,demand:$('demand').value});
  const r=await apiFetch('/api/network?'+query);if(!r.ok)throw Error('Jaringan tidak tersedia');const net=await r.json();if(revision!==mapRequest)return;
  state.network=net;state.case=net.case;mapRevision=query.toString();
  const profile=net.case.profile,main=new Set([profile.decision,...profile.main]),bypass=new Set(profile.paths.flat());
  for(const id of ['roads','junctions','workzone','labels','signals'])$(id).replaceChildren();clearFrames();
  for(const edge of net.edges)for(const lane of edge.lanes)$('roads').append(polyline(lane.shape,'road-edge',lane.width+1));
  for(const j of net.junctions)$('junctions').append(svgEl('polygon',{points:j.shape.map(([x,y])=>`${x},${-y}`).join(' '),fill:'#303a47'}));
  for(const edge of net.edges)for(const lane of edge.lanes){
    const kind=edge.internal?'':main.has(edge.id)?' main-lane':bypass.has(edge.id)?' bypass-lane':'';
    $('roads').append(polyline(lane.shape,'road-lane'+kind,lane.width-.16));
    if(!edge.internal)$('roads').append(polyline(lane.shape,'lane-guide',.10));
  }
  const bottle=net.edges.find(e=>e.id===profile.bottleneck),pre=net.edges.find(e=>e.id===profile.pre),junction=net.junctions.find(j=>j.id===(profile.junction||profile.tls));
  const shape=bottle.lanes[0].shape,mid=shape[Math.floor(shape.length/2)];
  const hazard=polyline(shape,'workzone-line',7);hazard.setAttribute('stroke','url(#hazard)');hazard.setAttribute('fill','none');hazard.setAttribute('opacity','.65');$('workzone').append(hazard);
  label(mid[0],-mid[1]-25,`GALIAN · ${net.case.lane_label||'2 → 1 lajur'}`,{'text-anchor':'middle'});
  if(junction){
    $('signals').append(svgEl('rect',{id:'junctionWarning',x:junction.x-14,y:-junction.y-14,width:28,height:28,fill:'transparent',stroke:'#ffd269','stroke-width':1,'stroke-dasharray':'3 2'}),svgEl('circle',{cx:junction.x,cy:-junction.y,r:4,class:'signal-light',id:'signal-light'}));
    label(junction.x,-junction.y-30,'SIMPANG KENDALI',{'text-anchor':'middle'});
  }
  const names=new Set();if(pre.name){const pts=pre.lanes[0].shape,pt=pts[Math.floor(pts.length/2)];label(pt[0]+18,-pt[1],pre.name);names.add(pre.name);}
  const named=new Map();for(const edge of net.edges){if(edge.internal||!edge.name||names.has(edge.name)||edge.lanes[0].shape.length<2)continue;const pts=edge.lanes[0].shape,pt=pts[Math.floor(pts.length/2)],distance=Math.hypot(pt[0]-mid[0],pt[1]-mid[1]);if(!named.has(edge.name)||distance<named.get(edge.name).distance)named.set(edge.name,{pt,distance});}
  for(const [name,{pt,distance}] of named)if(distance>70)label(pt[0],-pt[1]-12,name,{'text-anchor':'middle'});
  const all=net.edges.filter(e=>!e.internal).flatMap(e=>e.lanes.flatMap(l=>l.shape));
  views.all=bounds(all,80);views.corridor=bounds(net.edges.filter(e=>main.has(e.id)).flatMap(e=>e.lanes[0].shape),120);views.bottleneck=bounds([...pre.lanes[0].shape,...shape],75);views.junction=junction?[junction.x-280,-junction.y-180,560,360]:views.bottleneck;views.detail=[mid[0]-80,-mid[1]-48,160,96];
  setText('caseLabel',net.case.name);setText('caseTitle',`${net.case.demand_label} · ${net.case.planned_vehicles} kendaraan terjadwal`);setText('caseDescription',net.case.traffic_source);setText('caseMethod',profile.geographic?'Geometri OSM · pengaturan lampu dan galian untuk eksperimen':'Jaringan sintetik · kondisi sama untuk semua mode');setText('workzoneNote',`${fmt(net.case.bottleneck_length_m)} m · ${fmt(net.case.bottleneck_speed_kmh,1)} km/jam`);$('mapAttribution').hidden=!profile.geographic;
  setText('zoneLaneLabel',`Zona galian: ${net.case.lane_label||'2 → 1 lajur'}`);$('mapLocation').hidden=!profile.geographic||!profile.center;
  if(profile.center){const [lon,lat]=profile.center;$('mapLocation').href=`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;}
  chooseView('bottleneck');
  }finally{if(revision===mapRequest)$('map').setAttribute('aria-busy','false');}
}
function updateView(){
  $('map').setAttribute('viewBox',view.join(' '));
  const rect=$('map').getBoundingClientRect(),world=Math.max(view[2]/Math.max(rect.width,1),view[3]/Math.max(rect.height,1)),occupied=[];
  $('map').classList.toggle('close-up',world<.3);
  document.querySelectorAll('#labels text').forEach(t=>{
    t.style.fontSize=(13*world)+'px';t.style.strokeWidth=(3*world)+'px';
    const box=t.getBoundingClientRect();
    const inside=box.left>=rect.left+6&&box.right<=rect.right-6&&box.top>=rect.top+6&&box.bottom<=rect.bottom-34;
    const overlaps=occupied.some(b=>box.left<b.right+8&&box.right>b.left-8&&box.top<b.bottom+5&&box.bottom>b.top-5);
    t.style.visibility=inside&&!overlaps?'visible':'hidden';if(inside&&!overlaps)occupied.push(box);
  });
}
new ResizeObserver(updateView).observe($('mapContainer'));
function chooseView(name){view=[...views[name]];updateView();document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('selected',b.dataset.view===name));}
function zoom(factor){const [x,y,w,h]=view; const nw=Math.max(100,Math.min(16000,w*factor)),nh=nw*h/w;view=[x+(w-nw)/2,y+(h-nh)/2,nw,nh];updateView();}
let dragging=null;
$('map').addEventListener('pointerdown',e=>{if(e.button!==0)return;dragging={x:e.clientX,y:e.clientY,view:[...view]};$('map').setPointerCapture(e.pointerId);});
$('map').addEventListener('pointermove',e=>{if(!dragging)return;const rect=$('map').getBoundingClientRect();const scale=Math.min(rect.width/dragging.view[2],rect.height/dragging.view[3]);view=[dragging.view[0]-(e.clientX-dragging.x)/scale,dragging.view[1]-(e.clientY-dragging.y)/scale,...dragging.view.slice(2)];updateView();});
$('map').addEventListener('pointerup',()=>dragging=null);$('map').addEventListener('pointercancel',()=>dragging=null);
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>chooseView(b.dataset.view));
$('zoomIn').onclick=()=>zoom(.75);$('zoomOut').onclick=()=>zoom(1.3);
$('mapFullscreen').onclick=async()=>{if(document.fullscreenElement)await document.exitFullscreen();else if($('mapContainer').requestFullscreen)await $('mapContainer').requestFullscreen();else chooseView('bottleneck');};
function clearFrames(){frames=[];lastFrameReceived=0;for(const n of vehicleNodes.values())n.remove();vehicleNodes.clear();}
function acceptVehicles(t){
  if(!Array.isArray(t.vehicles_sample)||!Number.isFinite(t.updated))return;
  const stamp=t.updated*1000;if(frames.length&&stamp<=frames[frames.length-1].wall)return;
  if(frames.length){const gap=stamp-frames[frames.length-1].wall;if(gap>0&&gap<2500)packetInterval=packetInterval*.75+gap*.25;}
  frames.push({wall:stamp,vehicles:new Map(t.vehicles_sample.map(v=>[v.id,v]))});if(frames.length>20)frames.shift();lastFrameReceived=performance.now();
  setText('mapVehicleCount',`${t.vehicles_sample.length} / ${t.vehicles} kendaraan`);$('mapEmpty').hidden=!!t.vehicles_sample.length;
}
function carNode(v){
  let e=vehicleNodes.get(v.id);if(e)return e;
  const kind=v.kind==='truck'?'truck':v.kind==='delivery'||v.kind==='bus'?'van':'car';
  e=svgEl('g',{'data-id':v.id,class:'vehicle-model'});e.append(svgEl('use',{href:'#'+kind}));
  const title=svgEl('title');title.textContent=v.id;e.append(title);e.dataset.kind=kind;
  $('vehicles').append(e);vehicleNodes.set(v.id,e);return e;
}
function animate(now){
  if(!document.hidden&&frames.length){
    const latest=frames[frames.length-1];const running=state.telemetry.running;
    // Buffer roughly two packets. Interpolate between observed positions only;
    // never extrapolate traffic beyond the most recent SUMO measurement.
    const target=running?latest.wall+Math.min(now-lastFrameReceived,packetInterval*2)-Math.min(1700,Math.max(250,packetInterval*1.8)):latest.wall;
    let a=frames[0],b=a;
    for(const frame of frames){if(frame.wall<=target)a=frame;if(frame.wall>=target){b=frame;break;}b=frame;}
    const ratio=a===b?1:Math.max(0,Math.min(1,(target-a.wall)/(b.wall-a.wall)));
    const visible=new Set([...a.vehicles.keys(),...b.vehicles.keys()]);
    for(const [id,el] of vehicleNodes){if(!visible.has(id)){el.remove();vehicleNodes.delete(id);}}
    for(const id of visible){const va=a.vehicles.get(id),vb=b.vehicles.get(id),v=vb||va,p=va||v;
      const f=va&&vb?ratio:1;const x=p.x+(v.x-p.x)*f,y=p.y+(v.y-p.y)*f;
      const change=((v.angle-p.angle+540)%360)-180,angle=(p.angle||0)+change*f;
      const el=carNode(v);const index=[...id].reduce((n,c)=>n+c.charCodeAt(0),0)%palette.length;
      const color=v.rerouted?'#80ef95':palette[index];if(el.dataset.color!==color){el.style.color=color;el.dataset.color=color;}
      const radians=angle*Math.PI/180, length=v.length||4.6;
      const cx=x-Math.sin(radians)*length/2,cy=-y+Math.cos(radians)*length/2;
      const baseLength=el.dataset.kind==='truck'?8.5:el.dataset.kind==='van'?6:4.6;
      const scaleX=length/baseLength*1.25,scaleY=(v.width||1.8)/(el.dataset.kind==='truck'?2.4:el.dataset.kind==='van'?2:1.8)*1.25;
      const transform=`translate(${cx.toFixed(2)} ${cy.toFixed(2)}) rotate(${(angle-90).toFixed(1)}) scale(${scaleX.toFixed(2)} ${scaleY.toFixed(2)})`;
      if(el.dataset.transform!==transform){el.setAttribute('transform',transform);el.dataset.transform=transform;}
      const opacity=String(!va?ratio:!vb?1-ratio:1);if(el.style.opacity!==opacity)el.style.opacity=opacity;
    }
  }
  requestAnimationFrame(animate);
}
function chart(id,sets,colors,maxValue){
  const W=480,H=125,left=27,bottom=106,top=10; const max=maxValue||Math.ceil(Math.max(1,...sets.flat().filter(Number.isFinite))/10)*10;
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img"><path class="chart-grid" d="M${left} ${top}H475M${left} 58H475M${left} ${bottom}H475"/><text x="0" y="15" class="axis-label">${max}</text><text x="10" y="108" class="axis-label">0</text>`;
  for(let k=0;k<sets.length;k++){
    const values=sets[k];let path='',pen=false;values.forEach((v,i)=>{if(v==null||!Number.isFinite(v)){pen=false;return;}const x=left+(i/(values.length-1||1))*(W-left-5),y=bottom-v/max*(bottom-top);path+=`${pen?'L':'M'}${x.toFixed(1)},${y.toFixed(1)} `;pen=true;});
    s+=`<path d="${path}" class="chart-line" stroke="${colors[k]}"/>`;
  }
  $(id).innerHTML=s+'</svg>';
}
function renderCharts(t){const h=t.series||[],revision=`${t.run_id}:${h.at(-1)?.time}:${h.length}`;if(revision===lastSeriesTime)return;lastSeriesTime=revision;
  chart('queueChart',[h.map(x=>x.downstream),h.map(x=>x.upstream)],['#ffad6b','#ff758f']);
  chart('speedChart',[h.map(x=>x.downstream>0?x.speed:null)],['#6ed7ff'],60);setText('chartTime',`${fmt(h.at(-1)?.time)} detik`);
}
function renderEvents(t){const events=(t.events||[]).slice().reverse(),signature=JSON.stringify(events);if(signature===lastEvents)return;lastEvents=signature;
  $('events').replaceChildren();if(!events.length){setText('events','Belum ada tindakan agent pada sesi ini.');return;}
  for(const e of events){const row=document.createElement('div');row.className='event';const time=document.createElement('b'),message=document.createElement('span');time.textContent=`${e.time}s`;message.textContent=e.message;row.append(time,message);$('events').append(row);}
}
function comparable(run,reference){return run?.final?.finished===true&&run.run_id===run.final.run_id&&run.final.simulation_time===run.case?.duration&&run?.case?.signature===reference?.case?.signature&&run.seed===reference.seed&&run.sumo_version===reference.sumo_version&&run.final.simulation_time===reference.final.simulation_time&&(!(run.supervisor?.configured||reference.supervisor?.configured)||(Number.isFinite(run.final.gui_delay_ms)&&run.final.gui_delay_ms===reference.final.gui_delay_ms));}
function renderComparison(c,finished=Boolean(state.telemetry.finished)){
  const sig=JSON.stringify([c,finished,state.case.signature,state.telemetry.run_id,state.telemetry.scenario]);if(sig===lastComparison)return;lastComparison=sig;
  const panel=$('comparison');panel.hidden=true;
  const reference=c[state.telemetry.scenario]||c.baseline;
  if(!finished||!comparable(reference,reference)||reference.case?.signature!==state.case.signature||reference.run_id!==state.telemetry.run_id)return;
  const valid=Object.fromEntries(Object.entries(c).filter(([,run])=>comparable(run,reference)));
  if(Object.keys(valid).length<2)return;
  panel.hidden=false;setText('comparisonStatus',Object.keys(valid).length===3?'3 MODE SIAP':'2 MODE SIAP');
  const metrics=[['Trip selesai','completed_trips',0,''],['Waktu tunggu rata-rata','avg_waitingTime',1,' s'],['Waktu perjalanan rata-rata','avg_duration',1,' s'],['Total waktu kendaraan','total_vehicle_hours',2,' jam'],['Spillback','spillback_seconds',0,' s'],['Simpang terhambat','junction_blocked_seconds',0,' s'],['Tertahan masuk','pending',0,''],['Tabrakan','collisions',0,''],['Teleport','teleports',0,'']];
  $('comparisonRows').replaceChildren();
  for(const [title,key,digits,unit] of metrics){const tr=document.createElement('tr');const heading=document.createElement('th');heading.textContent=title;tr.append(heading);for(const mode of ['baseline','katup','hybrid']){const td=document.createElement('td');td.textContent=valid[mode]?fmt(valid[mode].summary[key],digits)+unit:c[mode]?.final?.finished?'Hasil tidak cocok':'Belum selesai';tr.append(td);}$('comparisonRows').append(tr);}
  const baseline=valid.baseline?.summary,heuristic=valid.katup?.summary;
  let verdict='Hasil tercatat sesuai percobaan, nilai lebih kecil lebih baik kecuali trip selesai.';
  let tradeoff=false;
  if(baseline&&heuristic){const change=baseline.completed_trips?(heuristic.completed_trips-baseline.completed_trips)/baseline.completed_trips*100:0,spill=heuristic.spillback_seconds-baseline.spillback_seconds,blocked=heuristic.junction_blocked_seconds-baseline.junction_blocked_seconds;verdict=`Trip selesai KATUP Heuristik ${change>=0?'naik':'turun'} ${fmt(Math.abs(change),1)}% dibanding baseline. Spillback ${spill>0?'bertambah':'berkurang'} ${fmt(Math.abs(spill))} s, hambatan simpang ${blocked>0?'bertambah':'berkurang'} ${fmt(Math.abs(blocked))} s.`;tradeoff=change<0||spill>0||blocked>0;}
  if(valid.hybrid&&!valid.hybrid.supervisor?.external_decisions)verdict+=' Hybrid memakai fallback heuristik, belum ada keputusan API LLM yang diterapkan.';
  $('resultVerdict').classList.toggle('tradeoff',tradeoff);setText('resultVerdict',verdict);setText('comparisonMethod',`Seed ${reference.seed} · ${reference.final.simulation_time} detik · ${reference.case.planned_vehicles} kendaraan · ${reference.sumo_version}. Rata-rata waktu berasal dari trip selesai, total jam-kendaraan termasuk kendaraan aktif dan tertahan.`);
}
function renderDecision(t){
  const ctrl=t.control||{},llm=t.supervisor||{};const hybrid=t.scenario==='hybrid';
  setText('strategyTitle',ctrl.last_action||'Mengamati antrean');setText('strategyReason',ctrl.strategy_reason||'Pengamat membaca antrean, Katup melindungi simpang, Rute memeriksa jalur alternatif.');
  setText('decisionSubtitle',modeLabels[t.scenario]||'Strategi dihitung dari kondisi simulasi');
  const profiles={balanced:'Seimbang',protect_downstream:'Lindungi hilir',relieve_upstream:'Urai antrean hulu',spread_routes:'Sebar arus'};
  const strategy=hybrid?`Strategi ${profiles[llm.profile]||'Seimbang'} · `:'';
  setText('strategyMeta',`${strategy}Target pengalihan ${fmt((ctrl.target_fraction||0)*100)}% kandidat · berhasil ${fmt(ctrl.rerouted)} kendaraan`);
  const labels={not_configured:'API BELUM AKTIF',waiting:'MENUNGGU API',active:'LLM AKTIF',fallback:'FALLBACK',disabled:'HEURISTIK'};
  statusClass($('llmStatus'),hybrid?(labels[llm.status]||'API BELUM AKTIF'):'HEURISTIK');
  setText('llmReason',hybrid?(llm.reason||'API belum dihubungkan, kendali tetap memakai heuristik'):t.scenario==='baseline'?'Pengamat mencatat kondisi, agen Katup dan Rute dinonaktifkan.':'Pengatur LLM digunakan pada mode KATUP Hybrid. Mode KATUP Heuristik memakai aturan tiga agen.');
  setText('llmRequests',llm.requests||0);setText('llmAccepted',llm.accepted||0);setText('llmLatency',llm.last_latency_ms==null?'—':`${llm.last_latency_ms} ms`);setText('llmTokens',(llm.input_tokens||0)+(llm.output_tokens||0));
  $('decisionHistory').replaceChildren();for(const event of (llm.history||[]).slice(-3).reverse()){const row=document.createElement('div');row.textContent=`${event.time}s · ${event.status==='accepted'?'Diterapkan':'Fallback'} · ${event.reason||'Tiga agen mengikuti heuristik'}`;$('decisionHistory').append(row);}
}
function render(t){const m=t.metrics||{},d=m.downstream||{},u=m.upstream||{},ctrl=t.control||{};
  setText('downstream',fmt(d.vehicles));setText('upstream',fmt(u.vehicles));setText('speedValue',d.vehicles===0?'—':fmt(d.speed_kmh,1));setText('rerouted',fmt(ctrl.rerouted));
  setText('mapSub',`${modeLabels[t.scenario]||'Belum berjalan'} · ${fmt(t.simulation_time)} / ${state.case.duration||1800} detik · ${fmt(t.vehicles)} kendaraan aktif`);
  $('liveDot').className='dot '+(t.running?'live':'');setText('liveLabel',t.running?'Simulasi berjalan':t.error?'Simulasi terganggu':t.finished?'Sesi selesai':'Belum berjalan');
  statusClass($('scenarioChip'),t.running?ctrl.mode||'RUNNING':t.finished?'SELESAI':'IDLE');statusClass($('obsStatus'),t.running?'ACTIVE':'WAITING');
  const active=t.running&&t.scenario!=='baseline';statusClass($('valveStatus'),active?ctrl.mode||'NORMAL':'DISABLED');statusClass($('routeStatus'),active?(ctrl.route_mode||'STANDBY'):'DISABLED');
  const observer=m.observer||{}, system=t.system||{};
  setText('queueMeters',`${fmt(observer.queue_m,1)} m`);setText('upstreamMeters',`${fmt(observer.upstream_queue_m,1)} m`);setText('pendingVehicles',fmt(system.pending));
  const spilling=!!observer.spillback,blocked=observer.junction_stopped>0;
  setText('spillbackStatus',blocked?'Kendaraan berhenti di dalam simpang':spilling?'Spillback: antrean mencapai simpang':'Ruas menuju simpang masih tersedia');
  $('spillbackStatus').classList.toggle('danger',spilling||blocked);
  const warning=$('junctionWarning');if(warning)warning.setAttribute('fill',blocked?'#ff758f55':'transparent');
  const phase=t.phase||{},index=phase.index;const schedule=state.case.profile?.phases||{},mains=schedule.main||[3],movement=schedule.movement_states?.[index];const green=movement?movement==='green':mains.includes(index),yellow=movement?movement==='yellow':mains.some(p=>index===p+1);setText('phaseText',index==null?'Belum ada fase':`Arah galian · ${green?'Hijau':yellow?'Kuning':'Merah'} · fase ${index}`);
  setText('phaseDetail',phase.next_switch?`Sisa fase ${fmt(Math.max(0,phase.next_switch-t.simulation_time),1)} detik`:'—');
  const signal=$('signal-light');if(signal)signal.style.fill=green?'#80ef95':yellow?'#ffd269':'#ff758f';
  $('lights').innerHTML=`<i class="light ${!green&&!yellow?'red':''}"></i><i class="light ${yellow?'yellow':''}"></i><i class="light ${green?'green':''}"></i>`;
  if(t.public_mode){$('desktop').hidden=true;setText('connection','Live · SUMO + TraCI');}
  if(t.running){if(t.scenario)$('mode').value=t.scenario;if(t.gui_delay_ms)$('speed').value=String(t.gui_delay_ms);}$('mode').disabled=!!t.running;$('speed').disabled=!!t.running;$('start').disabled=!!t.running;renderDecision(t);$('corridor').disabled=!!t.running;$('demand').disabled=!!t.running;renderCharts(t);renderEvents(t);renderComparison(state.comparison,Boolean(t.finished));$('stop').disabled=!t.running;
}
function accept(payload){
  const t=payload.telemetry||{};
  const incomingCase=t.case||payload.case;
  const mismatch=incomingCase&&(incomingCase.corridor!==$('corridor').value||incomingCase.demand!==$('demand').value);
  if(mismatch&&!t.running)return;
  if(mismatch&&t.running){$('corridor').value=incomingCase.corridor;$('demand').value=incomingCase.demand;buildMap().catch(()=>setText('mapSub','Peta gagal dimuat'));}
  const run=t.run_id||`${t.scenario}`;
  if(run!==currentRun){clearFrames();currentRun=run;lastSeriesTime=-1;state.telemetry={};}
  if((t.updated||0)<(state.telemetry.updated||0))return;
  state.telemetry={...state.telemetry,...t};if(payload.case)state.case=payload.case;
  if(payload.comparison)state.comparison=payload.comparison;
  acceptVehicles(state.telemetry);render(state.telemetry);
}
async function refresh(){try{const r=await apiFetch('/api/status');if(r.redirected){location.href=apiUrl('/login');return;}if(!r.ok)throw Error();const p=await r.json();p.telemetry={...p.telemetry,running:p.running,public_mode:p.public_mode};accept(p);}catch{setText('connection','Koneksi terputus. Mencoba menghubungkan kembali…');}}
function connectStream(){clearTimeout(retryTimer);stream=new WebSocket(socketUrl('/api/stream'));stream.onmessage=e=>{try{accept(JSON.parse(e.data));}catch(err){console.error(err);}};stream.onclose=()=>{retryTimer=setTimeout(connectStream,1800);};stream.onerror=()=>stream.close();}
async function command(path){
  $('start').disabled=true;$('stop').disabled=true;
  if(path.includes('/api/start/')){state.telemetry={};state.comparison={};lastComparison='';$('comparison').hidden=true;clearFrames();}
  try{const r=await apiFetch(path,{method:'POST'});if(!r.ok)throw Error(await r.text());await refresh();}catch{setText('liveLabel','Koneksi gagal, periksa backend');}finally{$('start').disabled=!!state.telemetry.running;$('stop').disabled=!state.telemetry.running;}
}
$('start').onclick=()=>command(`/api/start/${$('mode').value}?`+new URLSearchParams({delay_ms:$('speed').value,corridor:$('corridor').value,demand:$('demand').value}));$('stop').onclick=()=>command('/api/stop');
$('desktop').onclick=()=>{const base=new URL(API_BASE||location.origin,location.href);const port=base.port||({'https:':'443','http:':'80'}[base.protocol]||'');$('desktopModal').hidden=false;$('desktopFrame').src=`${base.origin}/novnc/vnc.html?host=${base.hostname}&port=${port}&path=websockify&resize=scale`;};$('closeDesktop').onclick=()=>{$('desktopModal').hidden=true;$('desktopFrame').src='';};
async function init(){
  try{const response=await apiFetch('/api/catalog');if(!response.ok)throw Error();const data=await response.json();
    for(const [id,items] of [['corridor',data.corridors],['demand',data.demands]]){const select=$(id);select.replaceChildren();for(const item of items){const option=document.createElement('option');option.value=item.id;option.textContent=item.name;select.append(option);}}
    $('corridor').value=data.selection.corridor;$('demand').value=data.selection.demand;
    await buildMap();await refresh();connectStream();
  }catch{setText('connection','Backend belum terhubung. Periksa alamat API dan koneksi VPS.');}
}
$('corridor').onchange=async()=>{state.telemetry={};state.comparison={};currentRun=null;lastComparison='';$('comparison').hidden=true;clearFrames();try{await buildMap();render({});}catch{setText('mapSub','Peta gagal dimuat');}};$('demand').onchange=$('corridor').onchange;
init();setInterval(()=>{if(!stream||stream.readyState!==WebSocket.OPEN)refresh();},4000);requestAnimationFrame(animate);
