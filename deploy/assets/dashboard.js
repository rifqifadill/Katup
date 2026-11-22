'use strict';
const $ = id => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const state = {telemetry: {}, comparison: {}};
let stream, retryTimer, lastSeriesTime = -1, lastComparison = '', lastEvents = '';
let frames = [], lastFrameReceived = 0, packetInterval = 250, currentRun = null;
const vehicleNodes = new Map();
const views = {corridor: [-340,-205,1020,390], bottleneck:[140,-85,290,170], junction:[-130,-110,450,220], detail:[180,-32,115,64], all:[-580,-355,1460,710]};
let view = [...views.corridor];
const palette = ['#cbdde9','#84b8ed','#f1d68d','#dda3ab','#b8c1cf','#a6d6d0'];
function svgEl(tag, attrs={}) {const e=document.createElementNS(NS,tag); for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;}
function setText(id, value){const e=$(id);if(e&&e.textContent!==String(value))e.textContent=value;}
function fmt(v,d=0){return v===undefined||v===null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d);}
function statusClass(el,status){el.textContent=status;el.className='status-chip '+(['ACTIVE','ADAPTIVE','KATUP_ACTIVE','SIAP'].includes(status)?'active':status==='RISIKO'?'warn':'');}
function polyline(points, cls, width){return svgEl('polyline',{points:points.map(([x,y])=>`${x},${-y}`).join(' '),class:cls,'stroke-width':width});}
async function buildMap(){
  const r=await fetch('/api/network');if(!r.ok)throw Error('Jaringan tidak tersedia'); const net=await r.json();
  const roads=$('roads');
  const main=new Set(['edge_W2J','edge_pre_bottle','edge_bottleneck','edge_bottle_exit','edge_post_merge']);
  const bypass=new Set(['edge_W2NW','edge_NW2N','edge_J2N','edge_alt_1','edge_alt_2','edge_alt2NE_east','edge_NE_east2E','edge_W2SW','edge_SW2S','edge_S2SE','edge_SE2E']);
  // Drawing actual SUMO lane centerlines preserves all lane counts and merge geometry.
  for(const e of net.edges){for(const lane of e.lanes){roads.append(polyline(lane.shape,'road-edge',lane.width+1));}}
  for(const j of net.junctions)$('junctions').append(svgEl('polygon',{points:j.shape.map(([x,y])=>`${x},${-y}`).join(' '),fill:'#263c4a'}));
  for(const e of net.edges){for(const lane of e.lanes){
    const kind=e.internal?'':main.has(e.id)?' main-lane':bypass.has(e.id)?' bypass-lane':'';
    roads.append(polyline(lane.shape,'road-lane'+kind,lane.width-.16));
    if(!e.internal)roads.append(polyline(lane.shape,'lane-guide',.10));
  }}
  const zone=$('workzone');
  zone.append(svgEl('path',{d:'M172,-6.2 L204,-.2 L350,-.2 L350,-7.8 L172,-7.8 Z',fill:'url(#hazard)',stroke:'#ffad6b','stroke-width':.5}));
  zone.append(svgEl('rect',{x:210,y:-11,width:130,height:3,rx:1,fill:'#342820',stroke:'#ed924c','stroke-width':.4}));
  for(let x=178;x<=350;x+=10){const y=x<204? -7.2+(x-178)/26*6.3:-.9;
    zone.append(svgEl('path',{d:`M${x},${y-1}l-1,2h2z`,fill:'#ff9b45',stroke:'#fff1bc','stroke-width':.3}));}
  for(const x of [190,250,310])zone.append(svgEl('path',{d:`M${x},5.8h10m-4,-1.2l4,1.2l-4,1.2`,stroke:'#e1e9ed','stroke-width':.5,fill:'none'}));
  const labels=[[-240,-28,'SIMPANG BARAT'],[-530,38,'VMS · PILIH RUTE DI HULU'],[-35,32,'KENDALI KATUP'],[38,-167,'BYPASS UTARA'],[265,-48,'GALIAN · 2 → 1 LAJUR'],[270,43,'Zona kerja 150 m · 5 km/jam'],[600,-28,'ARAH TIMUR']];
  for(const [x,y,name] of labels){const text=svgEl('text',{x,y,class:'road-label','text-anchor':name.startsWith('GALIAN')||name.startsWith('Zona kerja')?'middle':'start'});text.textContent=name;$('labels').append(text);}
  $('labels').append(svgEl('path',{d:'M265,-39V-13',stroke:'#f3a464','stroke-width':1,'stroke-dasharray':'3 3'}));
  $('signals').append(svgEl('rect',{id:'junctionWarning',x:-11,y:-11,width:22,height:22,fill:'transparent',stroke:'#ffd269','stroke-width':.7,'stroke-dasharray':'2 2'}));
  $('signals').append(svgEl('rect',{x:-20,y:10,width:21,height:8,rx:3,fill:'#101b25',stroke:'#537988','stroke-width':.6}),svgEl('circle',{cx:-15,cy:14,r:2,class:'signal-light',id:'signal-light'}));
}
function updateView(){ $('map').setAttribute('viewBox', view.join(' '));$('map').classList.toggle('close-up',view[2]<200); }
function chooseView(name){view=[...views[name]];updateView();document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('selected',b.dataset.view===name));}
function zoom(factor){const [x,y,w,h]=view; const nw=Math.max(100,Math.min(2200,w*factor)),nh=nw*h/w;view=[x+(w-nw)/2,y+(h-nh)/2,nw,nh];updateView();}
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
function renderComparison(c){const sig=JSON.stringify(c);if(sig===lastComparison)return;lastComparison=sig;
  const b=c.baseline||{},k=c.katup||{},bs=b.summary||{},ks=k.summary||{};const complete=Number.isFinite(bs.avg_duration)&&Number.isFinite(ks.avg_duration);
  const comparable=complete&&b.case?.signature&&b.case.signature===k.case?.signature&&b.seed===k.seed&&b.final?.simulation_time===k.final?.simulation_time&&b.sumo_version===k.sumo_version;
  statusClass($('comparisonStatus'),comparable?'SIAP':complete?'PERIKSA SEED':'Belum lengkap');
  setText('baseTrips',bs.completed_trips?`${bs.completed_trips} trip`:'—');setText('katupTrips',ks.completed_trips?`${ks.completed_trips} trip`:'—');
  if(!comparable)return;
  const bw=bs.avg_waitingTime,kw=ks.avg_waitingTime,bd=bs.avg_duration,kd=ks.avg_duration;
  function bars(baseId,controlId,a,b){const max=Math.max(a,b,1);$(baseId).style.width=`${a/max*100}%`;$(controlId).style.width=`${b/max*100}%`;}
  function delta(id,a,b){const pct=a?(b-a)/a*100:0;setText(id,`${pct>=0?'+':''}${fmt(pct,1)}%`);$(id).style.color=b>a?'var(--red)':'var(--mint)';}
  setText('waitCompare',`${fmt(bw,1)} s → ${fmt(kw,1)} s`);setText('durationCompare',`${fmt(bd,1)} s → ${fmt(kd,1)} s`);
  delta('waitDelta',bw,kw);delta('durationDelta',bd,kd);bars('baseWaitBar','waitBar',bw,kw);bars('baseDurationBar','durationBar',bd,kd);
  setText('systemCompare',`${fmt(bs.total_vehicle_hours,1)} → ${fmt(ks.total_vehicle_hours,1)} h`);delta('systemDelta',bs.total_vehicle_hours,ks.total_vehicle_hours);
  setText('spillCompare',`${bs.spillback_seconds} → ${ks.spillback_seconds} s`);
  setText('blockCompare',`${bs.junction_blocked_seconds} → ${ks.junction_blocked_seconds} s`);
  setText('pendingCompare',`${bs.pending} → ${ks.pending} kendaraan`);
  const better=kw<bw&&kd<bd&&ks.completed_trips>=bs.completed_trips&&ks.total_vehicle_hours<bs.total_vehicle_hours;
  setText('resultVerdict',better?'Pada skenario ini, KATUP menurunkan waktu tunggu, waktu perjalanan, dan total beban waktu jaringan, sekaligus meningkatkan trip selesai. Periksa juga spillback dan kendaraan tertahan di bawah.':'KATUP belum lebih baik secara keseluruhan pada sesi ini. Ruas hilir dapat lebih kosong, tetapi waktu tunggu dan antrean hulu tetap perlu diperiksa.');
  $('resultVerdict').classList.toggle('warning',!better);
  setText('comparisonMethod',`${b.case.name} · seed ${b.seed} · ${b.final.simulation_time} detik · ${b.case.planned_vehicles} kendaraan terjadwal. Waktu tunggu/perjalanan adalah rata-rata trip selesai. Total jam-kendaraan mencakup semua kendaraan, termasuk yang masih berjalan dan tertahan masuk. Input dan versi SUMO cocok pada kedua sesi.`);
}
function render(t){const m=t.metrics||{},d=m.downstream||{},u=m.upstream||{},ctrl=t.control||{};
  setText('downstream',fmt(d.vehicles));setText('upstream',fmt(u.vehicles));setText('speedValue',d.vehicles===0?'—':fmt(d.speed_kmh,1));setText('rerouted',fmt(ctrl.rerouted));
  setText('mapSub',`${t.scenario==='katup'?'Dengan KATUP':'Tanpa KATUP'} · ${fmt(t.simulation_time)} / 1800 detik · ${fmt(t.vehicles)} kendaraan aktif`);
  $('liveDot').className='dot '+(t.running?'live':'');setText('liveLabel',t.running?'Simulasi berjalan':t.error?'Simulasi terganggu':t.finished?'Sesi selesai':'Belum berjalan');
  statusClass($('scenarioChip'),t.running?ctrl.mode||'RUNNING':t.finished?'SELESAI':'IDLE');statusClass($('obsStatus'),t.running?'ACTIVE':'WAITING');
  const active=t.running&&t.scenario==='katup';statusClass($('valveStatus'),active?ctrl.mode||'NORMAL':'DISABLED');statusClass($('routeStatus'),active?(ctrl.route_mode||'STANDBY'):'DISABLED');
  const observer=m.observer||{}, system=t.system||{};
  setText('queueMeters',`${fmt(observer.queue_m,1)} m`);setText('upstreamMeters',`${fmt(observer.upstream_queue_m,1)} m`);setText('pendingVehicles',fmt(system.pending));
  const spilling=!!observer.spillback,blocked=observer.junction_stopped>0;
  setText('spillbackStatus',blocked?'Kendaraan berhenti di dalam simpang':spilling?'Spillback: antrean mencapai simpang':'Ruas menuju simpang masih tersedia');
  $('spillbackStatus').classList.toggle('danger',spilling||blocked);
  const warning=$('junctionWarning');if(warning)warning.setAttribute('fill',blocked?'#ff758f55':'transparent');
  const phase=t.phase||{},index=phase.index;const green=index===3,yellow=index===4;setText('phaseText',index==null?'Belum ada fase':`Arah barat · ${green?'Hijau':yellow?'Kuning':'Merah'} · fase ${index}`);
  setText('phaseDetail',phase.next_switch?`Sisa fase ${fmt(Math.max(0,phase.next_switch-t.simulation_time),1)} detik`:'—');
  const signal=$('signal-light');if(signal)signal.style.fill=green?'#80ef95':yellow?'#ffd269':'#ff758f';
  $('lights').innerHTML=`<i class="light ${!green&&!yellow?'red':''}"></i><i class="light ${yellow?'yellow':''}"></i><i class="light ${green?'green':''}"></i>`;
  if(t.public_mode){$('desktop').hidden=true;setText('connection','Dashboard publik · satu sesi bersama · HTTPS');}
  renderCharts(t);renderEvents(t);$('stop').disabled=!t.running;
}
function accept(payload){const t=payload.telemetry||{};const run=t.run_id||`${t.scenario}`;
  if(run!==currentRun){clearFrames();currentRun=run;lastSeriesTime=-1;state.telemetry={};}
  // HTTP fallback can arrive after a newer WebSocket frame.
  if((t.updated||0)<(state.telemetry.updated||0))return;
  state.telemetry={...state.telemetry,...t};if(payload.comparison){state.comparison=payload.comparison;renderComparison(payload.comparison);}
  acceptVehicles(state.telemetry);render(state.telemetry);
}
async function refresh(){try{const r=await fetch('/api/status');if(r.redirected){location='/login';return;}const p=await r.json();p.telemetry={...p.telemetry,running:p.running,public_mode:p.public_mode};accept(p);}catch{setText('connection','Koneksi terputus. Mencoba menghubungkan kembali…');}}
function connectStream(){clearTimeout(retryTimer);const protocol=location.protocol==='https:'?'wss':'ws';stream=new WebSocket(`${protocol}://${location.host}/api/stream`);stream.onmessage=e=>{try{accept(JSON.parse(e.data));}catch(err){console.error(err);}};stream.onclose=()=>{retryTimer=setTimeout(connectStream,1800);};stream.onerror=()=>stream.close();}
async function command(path){$('start').disabled=true;try{const r=await fetch(path,{method:'POST'});if(!r.ok)throw Error(await r.text());await refresh();}catch{setText('liveLabel','Perintah gagal, coba lagi');}finally{$('start').disabled=false;}}
$('start').onclick=()=>command(`/api/start/${$('mode').value}?delay_ms=${$('speed').value}`);$('stop').onclick=()=>command('/api/stop');
$('desktop').onclick=()=>{$('desktopModal').hidden=false;$('desktopFrame').src=`/novnc/vnc.html?host=${location.hostname}&port=${location.port}&path=websockify&resize=scale`;};$('closeDesktop').onclick=()=>{$('desktopModal').hidden=true;$('desktopFrame').src='';};
buildMap().catch(()=>setText('mapSub','Peta gagal dimuat. Muat ulang halaman.'));chooseView(innerWidth<621?'bottleneck':'corridor');refresh();connectStream();setInterval(()=>{if(!stream||stream.readyState!==WebSocket.OPEN)refresh();},4000);requestAnimationFrame(animate);
