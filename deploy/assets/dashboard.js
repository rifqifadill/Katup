'use strict';
const $ = id => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const API_BASE = String(window.KATUP_CONFIG?.apiBase || '').replace(/\/+$/, '');
const state = {telemetry: {}, comparison: {}, case: {}, network: null, aiConfig: {configured:false}};
const modeLabels={baseline:'Tanpa KATUP',katup:'Dengan KATUP',hybrid:'KATUP + AI'};
let mapRequest=0;
let stream, retryTimer, lastComparison='';
let frames = [], lastFrameReceived = 0, packetInterval = 250, currentRun = null;
const vehicleNodes = new Map();
const views={bottleneck:[140,-85,290,170],junction:[-130,-110,450,220],all:[-580,-355,1460,710]};
let view=[...views.bottleneck];
const palette = ['#cbdde9','#84b8ed','#f1d68d','#dda3ab','#b8c1cf','#a6d6d0'];
function apiUrl(path){return API_BASE ? `${API_BASE}${path.startsWith('/')?path:`/${path}`}` : path;}
function apiFetch(path, options={}){return fetch(apiUrl(path), {...options, credentials:'include'});}
function socketUrl(path){const base=new URL(API_BASE||location.origin, location.href);base.protocol=base.protocol==='https:'?'wss':base.protocol==='http:'?'ws':base.protocol;base.pathname=path;base.search='';base.hash='';return base.toString();}
function svgEl(tag, attrs={}) {const e=document.createElementNS(NS,tag); for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;}
function setText(id, value){const e=$(id);if(e&&e.textContent!==String(value))e.textContent=value;}
const numberFormats=[0,1,2].map(d=>new Intl.NumberFormat('id-ID',{minimumFractionDigits:d,maximumFractionDigits:d}));
function fmt(v,d=0){return v==null||!Number.isFinite(Number(v))?'—':numberFormats[d].format(Number(v));}
function clock(v){const s=Math.max(0,Math.floor(Number(v)||0));return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;}
function polyline(points, cls, width){return svgEl('polyline',{points:points.map(([x,y])=>`${x},${-y}`).join(' '),class:cls,'stroke-width':width});}
function bounds(points,pad=80){const xs=points.map(p=>p[0]),ys=points.map(p=>-p[1]);const x=Math.min(...xs)-pad,y=Math.min(...ys)-pad,w=Math.max(120,Math.max(...xs)-x+pad),h=Math.max(90,Math.max(...ys)-y+pad);return [x,y,w,h];}
function label(x,y,name,extra={}){const t=svgEl('text',{x,y,class:'road-label',...extra});t.textContent=name;$('labels').append(t);}
async function buildMap(){
  const revision=++mapRequest;
  $('map').setAttribute('aria-busy','true');
  try{
  const query=new URLSearchParams({corridor:$('corridor').value,demand:$('demand').value});
  const r=await apiFetch('/api/network?'+query);if(!r.ok)throw Error('Jaringan tidak tersedia');const net=await r.json();if(revision!==mapRequest)return;
  state.network=net;state.case=net.case;
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
  views.all=bounds(all,80);views.bottleneck=bounds([...pre.lanes[0].shape,...shape],75);views.junction=junction?[junction.x-280,-junction.y-180,560,360]:views.bottleneck;
  setText('caseLabel',net.case.name);setText('mapSub',profile.geographic?'Peta jalan asli · arus dan galian disimulasikan':'Jaringan uji · arus dan galian disimulasikan');$('mapAttribution').hidden=!profile.geographic;
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
function clearFrames(){frames=[];lastFrameReceived=0;for(const n of vehicleNodes.values())n.remove();vehicleNodes.clear();setText('mapVehicleCount','Belum ada kendaraan');$('mapEmpty').hidden=false;}
function acceptVehicles(t){
  if(!Array.isArray(t.vehicles_sample)||!Number.isFinite(t.updated))return;
  const stamp=t.updated*1000;if(frames.length&&stamp<=frames[frames.length-1].wall)return;
  if(frames.length){const gap=stamp-frames[frames.length-1].wall;if(gap>0&&gap<2500)packetInterval=packetInterval*.75+gap*.25;}
  frames.push({wall:stamp,vehicles:new Map(t.vehicles_sample.map(v=>[v.id,v]))});if(frames.length>20)frames.shift();lastFrameReceived=performance.now();
  setText('mapVehicleCount',`${fmt(t.vehicles)} kendaraan di jalan`);$('mapEmpty').hidden=!!t.vehicles_sample.length;setText('mapEmpty',t.finished?'Simulasi selesai.':t.running?'Kendaraan mulai masuk…':'Tekan Mulai untuk melihat lalu lintas.');
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
    // tahan beberapa paket, trus gerakin mobil di antara posisi SUMO yg udah diterima
    // jangan nebak posisi yg belum dikirim SUMO
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
function comparable(run,reference){return run?.final?.finished===true&&run.run_id===run.final.run_id&&run.final.simulation_time===run.case?.duration&&run?.case?.signature===reference?.case?.signature&&run.seed===reference.seed&&run.sumo_version===reference.sumo_version&&run.final.simulation_time===reference.final.simulation_time&&(!(run.supervisor?.configured||reference.supervisor?.configured)||(Number.isFinite(run.final.gui_delay_ms)&&run.final.gui_delay_ms===reference.final.gui_delay_ms));}
function renderComparison(c,finished=Boolean(state.telemetry.finished)){
  const sig=JSON.stringify([c,finished,state.case.signature,state.telemetry.run_id,state.telemetry.scenario]);if(sig===lastComparison)return;lastComparison=sig;
  const panel=$('comparison');panel.hidden=true;
  const reference=c[state.telemetry.scenario]||c.baseline;
  if(!finished||!comparable(reference,reference)||reference.case?.signature!==state.case.signature||reference.run_id!==state.telemetry.run_id)return;
  const valid=Object.fromEntries(Object.entries(c).filter(([,run])=>comparable(run,reference)));
  if(Object.keys(valid).length<2)return;
  panel.hidden=false;setText('comparisonStatus',`${Object.keys(valid).length} mode selesai`);
  const metrics=[['Kendaraan sampai tujuan','completed_trips',0,1,''],['Rata-rata waktu perjalanan','avg_duration',1,60,' menit'],['Rata-rata waktu menunggu','avg_waitingTime',1,60,' menit'],['Antrean mencapai simpang','spillback_seconds',0,1,' detik'],['Simpang terhalang','junction_blocked_seconds',0,1,' detik']];
  $('comparisonRows').replaceChildren();
  for(const [title,key,digits,divisor,unit] of metrics){
    const tr=document.createElement('tr'),heading=document.createElement('th');heading.textContent=title;heading.scope='row';tr.append(heading);
    for(const mode of ['baseline','katup','hybrid']){
      const td=document.createElement('td'),value=valid[mode]?.summary?.[key];
      td.textContent=valid[mode]?(value==null?'—':fmt(value/divisor,digits)+unit):c[mode]?.final?.finished?'Kondisi berbeda':'Belum diuji';tr.append(td);
    }
    $('comparisonRows').append(tr);
  }
  const baseline=valid.baseline?.summary,katup=valid.katup?.summary;
  let verdict='Bandingkan hasil tiap mode pada tabel di bawah.',tradeoff=false;
  if(baseline&&katup){
    const change=baseline.completed_trips?(katup.completed_trips-baseline.completed_trips)/baseline.completed_trips*100:null;
    const spill=katup.spillback_seconds-baseline.spillback_seconds,blocked=katup.junction_blocked_seconds-baseline.junction_blocked_seconds;
    const parts=[change==null?`Dengan KATUP, ${fmt(katup.completed_trips)} kendaraan sampai tujuan.`:change===0?'Jumlah kendaraan sampai tujuan tetap sama.':`Dengan KATUP, kendaraan sampai tujuan ${change>0?'naik':'turun'} ${fmt(Math.abs(change),1)}%.`];
    for(const [name,delta] of [['Antrean yang mencapai simpang',spill],['Waktu simpang terhalang',blocked]])parts.push(delta===0?`${name} tetap sama.`:`${name} ${delta>0?'bertambah':'berkurang'} ${fmt(Math.abs(delta))} detik.`);
    verdict=parts.join(' ');tradeoff=(change!=null&&change<0)||spill>0||blocked>0;
  }
  $('resultVerdict').classList.toggle('tradeoff',tradeoff);setText('resultVerdict',verdict);
  let method=`Setiap mode memakai ${fmt(reference.case.planned_vehicles)} kendaraan terjadwal selama ${fmt(reference.final.simulation_time/60)} menit. Rata-rata waktu dihitung dari kendaraan yang sudah sampai.`;
  if(valid.hybrid&&!valid.hybrid.supervisor?.external_decisions)method+=' Mode AI belum memakai saran AI, hasilnya mengikuti aturan KATUP.';
  setText('comparisonMethod',method);
}
function renderAI(t){
  const note=$('aiNote');note.hidden=$('mode').value!=='hybrid';if(note.hidden)return;
  const llm=t.scenario==='hybrid'?t.supervisor||{}:{};
  if(!state.aiConfig.configured)setText('aiNote','AI belum terhubung. Simulasi tetap memakai aturan KATUP.');
  else if(llm.status==='fallback')setText('aiNote','AI sedang tidak tersedia. Aturan KATUP tetap berjalan.');
  else if(llm.status==='active')setText('aiNote','AI membantu memilih strategi lalu lintas.');
  else setText('aiNote',t.running?'AI sedang membaca kondisi jalan.':'Mode AI siap digunakan.');
}
function render(t){
  const observer=t.metrics?.observer||{},ctrl=t.control||{},hasData=Number.isFinite(t.step)&&t.step>0;
  setText('queueMeters',fmt(observer.queue_m));setText('upstreamMeters',fmt(observer.upstream_queue_m));setText('rerouted',fmt(hasData?ctrl.rerouted:null));
  setText('simulationClock',`${clock(t.simulation_time)} / ${clock(state.case.duration||1800)}`);
  $('liveDot').className='dot '+(t.running?'live':'');setText('liveLabel',t.error?'Simulasi terhenti':t.running?'Sedang berjalan':t.finished?'Selesai':hasData?'Dihentikan':'Belum dimulai');
  setText('summaryCaption',hasData?`${t.running?'Sedang berjalan':'Kondisi terakhir'} · ${modeLabels[t.scenario]||'Simulasi'}`:'Belum ada simulasi');
  const blocked=observer.junction_stopped>0,spilling=!!observer.spillback;
  setText('trafficStatus',!hasData?'Menunggu simulasi':blocked?'Simpang terhalang kendaraan':spilling?'Antrean mendekati simpang':'Simpang masih terbuka');
  $('trafficStatus').className='traffic-status '+(hasData?(blocked||spilling?'danger':'clear'):'');
  const warning=$('junctionWarning');if(warning)warning.setAttribute('fill',blocked?'#ff758f55':'transparent');
  const actions={'Memantau antrean dua arah':'Memantau antrean lalu lintas.','Menahan arus masuk galian':'Menahan kendaraan agar simpang tetap terbuka.','Melayani arus silang':'Memberi giliran untuk arah lain.','Melayani arus utama setelah antrean silang terlayani':'Membuka jalan menuju galian.'};
  setText('actionText',!hasData?'Mulai simulasi untuk melihat pengaturan lalu lintas.':t.scenario==='baseline'?'Lampu memakai durasi tetap.':actions[ctrl.last_action]||ctrl.last_action||'Memantau antrean lalu lintas.');
  const index=t.phase?.index,schedule=state.case.profile?.phases||{},mains=schedule.main||[3],movement=schedule.movement_states?.[index],known=Number.isInteger(index);
  const green=known&&(movement?movement==='green':mains.includes(index)),yellow=known&&(movement?movement==='yellow':mains.some(p=>index===p+1));
  setText('phaseText',!known?'—':green?'Hijau':yellow?'Kuning':'Merah');
  const signal=$('signal-light');if(signal)signal.style.fill=!known?'#687581':green?'#80ef95':yellow?'#ffd269':'#ff758f';
  $('lights').innerHTML=`<i class="light ${known&&!green&&!yellow?'red':''}"></i><i class="light ${yellow?'yellow':''}"></i><i class="light ${green?'green':''}"></i>`;
  if(t.running){if(t.scenario)$('mode').value=t.scenario;if(t.gui_delay_ms)$('speed').value=String(t.gui_delay_ms);}
  for(const id of ['mode','speed','start','corridor','demand'])$(id).disabled=!!t.running;
  $('stop').disabled=!t.running;renderAI(t);renderComparison(state.comparison,Boolean(t.finished));
}
function accept(payload){
  const t=payload.telemetry||{},incomingCase=t.case||payload.case;
  const mismatch=incomingCase&&(incomingCase.corridor!==$('corridor').value||incomingCase.demand!==$('demand').value);
  if(mismatch&&!t.running)return;
  if(mismatch&&t.running){$('corridor').value=incomingCase.corridor;$('demand').value=incomingCase.demand;buildMap().catch(()=>setText('mapSub','Peta belum bisa dimuat.'));}
  const run=t.run_id||`${t.scenario}`;
  if(run!==currentRun){clearFrames();currentRun=run;state.telemetry={};}
  if((t.updated||0)<(state.telemetry.updated||0))return;
  state.telemetry={...state.telemetry,...t};if(payload.case)state.case=payload.case;
  if(payload.comparison)state.comparison=payload.comparison;
  acceptVehicles(state.telemetry);render(state.telemetry);
}
async function refresh(){try{const r=await apiFetch('/api/status');if(r.redirected){location.href=apiUrl('/login');return;}if(!r.ok)throw Error();const p=await r.json();p.telemetry={...p.telemetry,running:p.running,public_mode:p.public_mode};accept(p);setText('connection','Terhubung');}catch{setText('connection','Koneksi terputus, mencoba kembali…');}}
function connectStream(){clearTimeout(retryTimer);stream=new WebSocket(socketUrl('/api/stream'));stream.onopen=()=>setText('connection','Terhubung');stream.onmessage=e=>{try{accept(JSON.parse(e.data));}catch(err){console.error(err);}};stream.onclose=()=>{setText('connection','Koneksi terputus, mencoba kembali…');retryTimer=setTimeout(connectStream,1800);};stream.onerror=()=>stream.close();}
async function command(path){
  $('start').disabled=true;$('stop').disabled=true;
  if(path.includes('/api/start/')){state.telemetry={};state.comparison={};lastComparison='';$('comparison').hidden=true;clearFrames();}
  try{const r=await apiFetch(path,{method:'POST'});if(!r.ok)throw Error(await r.text());await refresh();}catch{setText('liveLabel','Perintah belum berhasil, coba lagi.');}finally{$('start').disabled=!!state.telemetry.running;$('stop').disabled=!state.telemetry.running;}
}
$('start').onclick=()=>command(`/api/start/${$('mode').value}?`+new URLSearchParams({delay_ms:$('speed').value,corridor:$('corridor').value,demand:$('demand').value}));$('stop').onclick=()=>command('/api/stop');
$('mode').onchange=()=>renderAI(state.telemetry);
async function init(){
  try{const response=await apiFetch('/api/catalog');if(!response.ok)throw Error();const data=await response.json();state.aiConfig=data.llm;
    for(const [id,items] of [['corridor',data.corridors],['demand',data.demands]]){const select=$(id);select.replaceChildren();for(const item of items){const option=document.createElement('option');option.value=item.id;option.textContent=item.name;select.append(option);}}
    $('corridor').value=data.selection.corridor;$('demand').value=data.selection.demand;
    await buildMap();await refresh();connectStream();
  }catch{setText('connection','Simulasi belum bisa dihubungi. Coba muat ulang.');}
}
$('corridor').onchange=async()=>{state.telemetry={};state.comparison={};currentRun=null;lastComparison='';$('comparison').hidden=true;clearFrames();try{await buildMap();render({});}catch{setText('mapSub','Peta belum bisa dimuat.');}};$('demand').onchange=$('corridor').onchange;
init();setInterval(()=>{if(!stream||stream.readyState!==WebSocket.OPEN)refresh();},4000);requestAnimationFrame(animate);
