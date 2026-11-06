'use strict';
const $=s=>document.querySelector(s), csrf=$('meta[name=csrf]').content;
let state={},user={},shown=new Date(),view='calendar';
const searches={calendar:{query:'',sector:'',type:''},employees:{query:''},absences:{query:'',sector:'',type:''}};
const normalizeName=value=>String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('es-AR').trim().replace(/\s+/g,' ');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const fmt=s=>s?new Date(s+'T12:00:00').toLocaleDateString('es-AR'):'—';
const full=e=>`${e.first} ${e.last}`, person=id=>state.employees.find(e=>e.id===id), admin=()=>user.role==='admin';
const initials=e=>(e.first[0]+e.last[0]).toUpperCase();
const opt=(v,label=v,selected=false)=>`<option value="${esc(v)}" ${selected?'selected':''}>${esc(label)}</option>`;
const field=(label,name,value='',type='text',extra='')=>`<label>${esc(label)}<input type="${type}" name="${name}" value="${esc(value)}" ${extra}></label>`;
function notice(text,error=false){$('#notice').hidden=false;$('#notice').textContent=text;$('#notice').className=error?'error':'';}
async function api(path,body){const options={headers:{'X-CSRF-Token':csrf}};if(body!==undefined){options.method='POST';if(body instanceof FormData)options.body=body;else{options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}}const r=await fetch('/api/'+path,options);const data=await r.json();if(!r.ok){const e=new Error(data.error||'No se pudo completar la operación.');e.data=data;e.status=r.status;throw e;}return data;}
function modal(title,html){$('#modal-title').textContent=title;$('#modal-body').innerHTML=html;if(!$('#modal').open)$('#modal').showModal();}
$('#close').onclick=()=>$('#modal').close();
function form(title,html,save){modal(title,`<form id="editor"><div class="form-grid">${html}</div><p id="form-error" class="error" role="alert"></p><div class="actions"><button type="button" id="cancel">Volver</button><button class="primary">Guardar</button></div></form>`);$('#cancel').onclick=()=>$('#modal').close();$('#editor').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await save(Object.fromEntries(new FormData(e.target)));$('#modal').close();await refresh();notice('Cambios guardados.');}catch(err){$('#form-error').textContent=err.message;}finally{b.disabled=false;}};}
async function init(){try{user=await api('session');$('#auth').hidden=!!user.user;$('#app').hidden=!user.user;if(!user.user){$('#auth-title').textContent=user.setup?'Empecemos con tu equipo':'Bienvenida de nuevo';$('#auth-help').textContent=user.setup?'Creá el usuario administrador. Usá una contraseña de al menos 12 caracteres.':'Ingresá para organizar vacaciones y licencias.';$('#login button').textContent=user.setup?'Crear administrador':'Ingresar';return;}$('#identity').textContent=`${user.user} · ${admin()?'Administración':'Solo lectura'}`;document.querySelectorAll('.admin').forEach(el=>el.hidden=!admin());await refresh();}catch(e){notice(e.message,true);}}
$('#login').onsubmit=async e=>{e.preventDefault();const p=Object.fromEntries(new FormData(e.target));try{if(user.setup)await api('setup',p);await api('login',p);await init();}catch(err){$('#auth-error').textContent=err.message;}};
$('#logout').onclick=async()=>{await api('logout',{});location.reload();};
$('#year').value=new Date().getFullYear();
async function refresh(){state=await api('data?year='+$('#year').value);const sector=$('#sector').value;$('#sector').innerHTML=opt('','Todos los sectores')+[...new Set(state.employees.map(e=>e.sector))].sort().map(s=>opt(s,s,s===sector)).join('');const type=$('#type').value;$('#type').innerHTML=opt('','Todos los tipos')+state.types.map(t=>opt(t.name,t.name,t.name===type)).join('');for(const k of ['active','current','next'])$('#stat-'+k).textContent=state.stats[k];for(const key of ['current','next'])$('#stat-'+key+'-detail').textContent=`${state.stats[key+'_detail'].vacations} vacaciones · ${state.stats[key+'_detail'].leaves} licencias`;render();}
function matches(e,target){
  if(!e)return false;
  const filters=searches[target],name=normalizeName(full(e)),words=normalizeName(filters.query).split(' ').filter(Boolean);
  return words.every(word=>name.includes(word))&&(!filters.sector||e.sector===filters.sector);
}
function filteredAbsences(target='absences'){
  const filters=searches[target];
  return state.absences.filter(a=>matches(person(a.employee),target)&&(!filters.type||a.type===filters.type));
}
function employeeResults(){
  return state.employees.filter(e=>matches(e,'employees')&&($('#active-filter').value===''||String(e.active)===$('#active-filter').value));
}
function renderSearchStatus(){
  if(!searches[view])return;
  const q=searches[view].query;
  let count;
  if(view==='employees')count=employeeResults().length;
  else if(view==='absences')count=filteredAbsences().length;
  else{
    const first=iso(new Date(shown.getFullYear(),shown.getMonth(),1)),last=iso(new Date(shown.getFullYear(),shown.getMonth()+1,0));
    count=filteredAbsences('calendar').filter(a=>!['Canceladas','Rechazadas'].includes(a.state)&&a.start<=last&&a.end>=first).length;
  }
  const noun=view==='employees'?(count===1?'empleado':'empleados'):(count===1?'ausencia':'ausencias');
  $('#search-status').textContent=`Resultados: ${count} ${noun}${q?' para «'+q+'»':''}.`;
}
function render(){renderCalendar();renderEmployees();renderAbsences();renderTypes();renderSearchStatus();}
function renderCalendar(){const y=shown.getFullYear(),m=shown.getMonth();$('#month-title').textContent=shown.toLocaleDateString('es-AR',{month:'long',year:'numeric'});$('#month').value=`${y}-${String(m+1).padStart(2,'0')}`;const first=new Date(y,m,1),begin=new Date(y,m,1-(first.getDay()+6)%7),last=new Date(y,m+1,0);let html='';const records=filteredAbsences('calendar').filter(a=>!['Canceladas','Rechazadas'].includes(a.state));for(let w=0;w<6;w++){const ws=new Date(begin);ws.setDate(begin.getDate()+7*w);if(ws>last)break;const dates=Array.from({length:7},(_,i)=>{let d=new Date(ws);d.setDate(ws.getDate()+i);return d;});const start=iso(dates[0]),end=iso(dates[6]);let lanes=[],bars=[];const week=records.filter(a=>a.start<=end&&a.end>=start).sort((a,b)=>a.start.localeCompare(b.start)||a.id-b.id);for(const a of week){let l=dates.findIndex(d=>iso(d)>=a.start);if(l<0)l=0;let r=6;for(let i=6;i>=0;i--)if(iso(dates[i])<=a.end){r=i;break;}let lane=0;while(lanes[lane]?.some(([x,z])=>l<=z&&r>=x))lane++;(lanes[lane]??=[]).push([l,r]);bars.push({a,l,r,lane});}html+='<div class="week">'+dates.map((d,i)=>`<div style="grid-column:${i+1}" class="day ${d.getMonth()!==m?'outside':''} ${[0,6].includes(d.getDay())?'weekend':''}"><span class="date ${iso(d)===state.today?'today':''}">${d.getDate()}</span></div>`).join('')+'<div class="events">';for(const b of bars.filter(b=>b.lane<3)){const e=person(b.a.employee);html+=`<button class="event ${b.a.state==='Solicitadas'?'pending':b.a.type==='Vacaciones'?'':'leave'}" style="grid-column:${b.l+1}/${b.r+2};grid-row:${b.lane+1}" data-absence="${b.a.id}" title="${esc(full(e)+' · '+b.a.type)}">${esc(full(e))}</button>`;}dates.forEach((d,i)=>{const hidden=bars.filter(b=>b.lane>=3&&b.l<=i&&b.r>=i);if(hidden.length)html+=`<button class="event more" style="grid-column:${i+1};grid-row:4" data-day="${iso(d)}">+${hidden.length} más</button>`;});html+='</div></div>';}$('#calendar').innerHTML=html;bindAbsences($('#calendar'));document.querySelectorAll('[data-day]').forEach(b=>b.onclick=()=>{modal('Ausencias · '+fmt(b.dataset.day),records.filter(a=>a.start<=b.dataset.day&&a.end>=b.dataset.day).map(card).join(''));bindAbsences($('#modal-body'));});}
function card(a){const e=person(a.employee);return `<button class="card absence-card" data-absence="${a.id}"><div class="person"><span class="avatar">${esc(initials(e))}</span><div><strong>${esc(full(e))}</strong><br><small>${esc(e.sector)}</small></div></div><span class="badge ${a.type==='Vacaciones'?'':'license'}">${esc(a.type)}</span><br><small>${fmt(a.start)} → ${fmt(a.end)} · ${a.days} días</small><br><small>${esc(a.state)} · Período ${a.year}</small>${a.included_days?`<br><small>${a.included_days} días incluidos en saldo inicial · no se vuelven a descontar</small>`:''}</button>`;}
function bindAbsences(root){root.querySelectorAll('[data-absence]').forEach(b=>b.onclick=()=>absenceDetail(Number(b.dataset.absence)));}
function renderAbsences(){$('#absences').innerHTML=filteredAbsences().slice().reverse().map(card).join('')||'<p class="empty">Todavía no hay ausencias para estos filtros.</p>';bindAbsences($('#absences'));}
function renderEmployees(){let rows=employeeResults();const sort=$('#sort').value;rows.sort((a,b)=>sort==='available'?a.balance.available-b.balance.available:String(a[sort]).localeCompare(String(b[sort])));$('#employees').innerHTML=rows.map(e=>`<tr><td><button class="name-button person" data-employee="${e.id}"><span class="avatar">${esc(initials(e))}</span><span><strong>${esc(full(e))}</strong><small>${esc(e.code)} · ${e.active?'Activo':'Inactivo'}${e.demo?' · DEMO':''}</small></span></button></td><td>${fmt(e.hired)}<br><small>${e.seniority} años</small></td><td>${admin()?`<button class="name-button" data-accrual="${e.id}" title="Editar adquiridos y días del período">${e.balance.accrual.acquired} días ✎</button>`:`${e.balance.accrual.acquired} días`}<br><small>${e.balance.accrual.manual?'Manual':'Orientativo'} al ${fmt(e.balance.accrual.asof)}</small></td><td>${e.balance.accrual.assigned_manual?e.balance.assigned:e.balance.accrual.projected_closing} días<br><small>${e.balance.accrual.assigned_manual?'Asignación manual':'Proyección al 31/12'}</small></td><td>${e.balance.opening?`Saldo inicial: ${e.balance.opening.remaining}<br><small>Al ${fmt(e.balance.opening.cutoff)}</small>`:`${e.balance.assigned} + ${e.balance.adjustment}`}${e.balance.needs_review?' ⚠ Revisar':''}</td><td>${e.balance.used}</td><td>${e.balance.reserved}</td><td><span class="badge">${e.balance.available} días</span></td></tr>`).join('')||`<tr><td colspan="8" class="empty">${state.employees.length?'No se encontraron empleados con ese nombre o apellido y estado. Usá Limpiar o revisá el filtro de estado.':'Tu nómina empieza aquí. Agregá empleados o cargá la demostración desde Administración.'}</td></tr>`;document.querySelectorAll('[data-employee]').forEach(b=>b.onclick=()=>employeeDetail(Number(b.dataset.employee)));document.querySelectorAll('[data-accrual]').forEach(b=>b.onclick=()=>accrualForm(person(Number(b.dataset.accrual)),$('#year').value,person(Number(b.dataset.accrual)).balance));}
function employeeForm(e={active:1}){form(e.id?'Editar empleado':'Nuevo empleado',field('Identificador interno','code',e.code,'text','required')+field('Nombre','first',e.first,'text','required')+field('Apellido','last',e.last,'text','required')+field('Sector','sector',e.sector,'text','required')+field('Puesto','position',e.position,'text','required')+field('Fecha de ingreso','hired',e.hired,'date','required')+`<label>Estado<select name="active">${opt('1','Activo',!!e.active)+opt('0','Inactivo',!e.active)}</select></label><label class="full">Observaciones<textarea name="notes">${esc(e.notes)}</textarea></label>`,p=>api('employees',{...p,id:e.id,active:p.active==='1'}));}
function accrualForm(e,year,b){
  const a=b.accrual,r=a.record;
  form('Adquiridos y período · '+full(e),
    field('Período anual','year',year,'number','required min="1900" max="2200"')+
    field('Fecha del cómputo','asof',r?.asof??a.asof,'date',`required max="${state.today}"`)+
    field('Días trabajados / computables confirmados (opcional)','worked_days',r?.worked_days??'','number','min="0" step="1"')+
    field('Días adquiridos: corrección manual (opcional)','acquired',r?.acquired??'','number','min="0" step="0.5"')+
    field('Asignación exacta del período para el saldo (opcional)','assigned',a.assigned_manual?b.assigned:'','number','min="0" step="0.5"')+
    field('Motivo / validación de RR. HH.','reason',r?.reason??'','text','required')+
    `<p id="accrual-summary" class="opening-note full"></p><p class="help full">Son conceptos distintos: adquiridos indica el derecho calculado o confirmado a la fecha del cómputo; período/cierre indica el total anual o su proyección. No se suman entre sí. La estimación cuenta lunes a viernes, sin feriados ni asistencia; no acredita trabajo efectivo. Si corresponde el proporcional, se orienta a 1 día cada 20 computables. El período completo y las ausencias computables deben validarse según LCT, convenio y jornada real.</p><p class="help full">Dejá la corrección manual vacía para calcular desde los días computables, o completala (incluso con 0). Para autorizar días en el saldo disponible, completá la asignación exacta del período: no se aplican automáticamente estimaciones ni proyecciones. Se conservan ajustes y reservas. Si existe saldo inicial real, ese saldo sigue siendo la base y debe editarse por separado.</p><label class="full check"><input type="checkbox" name="reset">Volver al cómputo automático diario, quitando la corrección y el conteo guardados. La asignación anual se conserva.</label>`,
    async p=>{await api('accruals',{...p,employee:e.id,reset:p.reset==='on'});$('#year').value=p.year;}
  );
  const apply=b=>{const a=b.accrual,r=a.record,f=$('#editor');f.elements.asof.value=r?.asof??a.asof;f.elements.worked_days.value=r?.worked_days??'';f.elements.acquired.value=r?.acquired??'';f.elements.assigned.value=a.assigned_manual?b.assigned:'';f.elements.reason.value=r?.reason??'';f.elements.reset.checked=false;$('#accrual-summary').textContent=`Orientación al ${fmt(a.asof)}: ${a.estimated_acquired} días adquiridos con ${a.worked_days} días computables. Proyección al 31/12: ${a.projected_closing} días; tramo por antigüedad: ${a.full_entitlement}. Disponible según asignación/saldo inicial: ${b.available} días.`;};
  apply(b);balanceYearLoader(e,apply);
}
function employeeDetail(id){
  const e=person(id),b=e.balance,year=$('#year').value;
  const history=state.absences.filter(a=>a.employee===id&&a.year===Number(year));
  const metrics=b.opening?[['Saldo inicial',b.opening.remaining],['Ya incluidos',b.included_used],['Utilizados posteriores',b.deducted_used],['Reservados',b.reserved],['Disponibles',b.available]]:[['Asignados',b.assigned],['Ajustes',b.adjustment],['Utilizados',b.used],['Reservados',b.reserved],['Disponibles',b.available]];
  modal(full(e),`<p class="muted">${esc(e.code)} · ${esc(e.sector)} · ${esc(e.position)}</p><p>Ingreso: ${fmt(e.hired)} · Antigüedad: ${e.seniority} años · ${e.active?'Activo':'Inactivo'}</p><p>${esc(e.notes)}</p><h3>Vacaciones · período ${esc(year)}</h3><div class="balance-row"><div><small>Días adquiridos al ${fmt(b.accrual.asof)}</small><strong>${b.accrual.acquired}</strong><small>${b.accrual.manual?'Corrección manual':'Orientativo · '+esc(b.accrual.source)}</small></div><div><small>Correspondientes al período / cierre</small><strong>${b.accrual.assigned_manual?b.assigned:b.accrual.projected_closing}</strong><small>${b.accrual.assigned_manual?'Asignación manual':'Proyección al 31/12 · requiere validación'}</small></div></div><p class="help">Los adquiridos y la proyección no se suman al saldo disponible. Para autorizar su uso, editá la asignación del período o el saldo inicial real.</p><p class="help">Para consultar otros años, cambiá el período en la barra principal.</p>${b.needs_review?'<p class="error">RR. HH. debe revisar los días efectivamente trabajados y asignar el saldo de este período.</p>':''}<div class="balance-row">${metrics.map(([l,v])=>`<div><small>${l}</small><strong>${v}</strong></div>`).join('')}</div>${b.opening?`<p class="opening-note">Saldo real al cierre del <strong>${fmt(b.opening.cutoff)}</strong>. Las vacaciones hasta esa fecha ya están contempladas: se guardan en el historial sin descontarse de nuevo. Solo se descuentan los días posteriores al corte.</p><p class="help">Motivo: ${esc(b.opening.reason)}. Asignación anual conservada: ${b.assigned} + ${b.adjustment} (no se suma al saldo inicial).</p>`:`<p class="help">${esc(b.reason||'Asignación sugerida por antigüedad. Podés reemplazarla por los días exactos validados por RR. HH.')}</p>`}${admin()?'<div class="actions wrap"><button id="edit-person">Editar empleado</button><button id="edit-accrual">Editar adquiridos y período</button><button id="edit-balance">Editar días asignados</button><button id="opening-balance" class="primary">Cargar / editar saldo inicial real</button><button id="employee-planned">Registrar vacaciones futuras</button><button id="employee-history">Registrar vacaciones ya tomadas</button></div>':''}<h3>Vacaciones ya tomadas · ${esc(year)}</h3>${history.filter(a=>a.type==='Vacaciones'&&['Disfrutadas','Aprobadas'].includes(a.state)&&a.end<=state.today).map(card).join('')||'<p class="help">Sin vacaciones tomadas registradas en este período. Podés cargar meses anteriores sin perder el saldo inicial.</p>'}<h3>Otras vacaciones del período</h3>${history.filter(a=>a.type==='Vacaciones'&&!(['Disfrutadas','Aprobadas'].includes(a.state)&&a.end<=state.today)).map(card).join('')||'<p class="help">Sin otros registros.</p>'}<h3>Licencias · año calendario ${esc(year)}</h3><div class="balance-row"><div><small>Total aprobado / disfrutado</small><strong>${e.leaves.total}</strong></div><div><small>Utilizados</small><strong>${e.leaves.used}</strong></div><div><small>Reservados</small><strong>${e.leaves.reserved}</strong></div><div><small>Solicitados pendientes (aparte)</small><strong>${e.leaves.pending}</strong></div></div><p class="help">Días corridos dentro del año seleccionado. Las licencias no consumen vacaciones; rechazadas y canceladas no suman.</p>${Object.entries(e.leaves.by_type).map(([type,t])=>`<p>${esc(type)}: <strong>${t.total} días</strong> (${t.used} utilizados, ${t.reserved} reservados; ${t.pending} pendientes aparte)</p>`).join('')}${state.absences.filter(a=>a.employee===id&&a.type!=='Vacaciones'&&a.start<=year+'-12-31'&&a.end>=year+'-01-01').map(card).join('')||'<p class="help">Sin licencias en este año.</p>'}`);
  bindAbsences($('#modal-body'));
  if(admin()){
    $('#edit-accrual').onclick=()=>accrualForm(e,year,b);
    $('#edit-person').onclick=()=>employeeForm(e);
    $('#edit-balance').onclick=()=>annualBalanceForm(e,year,b);
    $('#opening-balance').onclick=()=>openingBalanceForm(e,year,b);
    $('#employee-planned').onclick=()=>absenceForm({employee:id,type:'Vacaciones',year,state:'Solicitadas',requested:state.today});
    $('#employee-history').onclick=()=>absenceForm({employee:id,type:'Vacaciones',year,state:'Disfrutadas',requested:state.today},true);
  }
}
function balanceYearLoader(e,apply){
  const f=$('#editor');let requested=f.elements.year.value,version=0;
  const load=async()=>{
    const year=f.elements.year.value;if(year===requested||!f.elements.year.checkValidity())return;
    requested=year;const ticket=++version,save=f.querySelector('button.primary');
    const fields=[...f.querySelectorAll('input,textarea,select')].filter(x=>x.name!=='year');
    fields.forEach(x=>x.disabled=true);save.disabled=true;$('#form-error').textContent='Cargando el período seleccionado…';
    let ok=false;
    try{
      const data=await api('data?year='+encodeURIComponent(year));
      if($('#editor')===f&&ticket===version&&f.elements.year.value===year){apply(data.employees.find(x=>x.id===e.id).balance);$('#form-error').textContent='';ok=true;}
    }catch(err){if($('#editor')===f&&ticket===version){$('#form-error').textContent=err.message;requested=null;}}
    finally{if($('#editor')===f&&ticket===version){fields.forEach(x=>x.disabled=false);save.disabled=!ok;}}
  };
  f.elements.year.oninput=load;f.elements.year.onchange=load;
}
function annualBalanceForm(e,year,b){
  form('Días asignados · '+full(e),field('Período anual','year',year,'number','required min="1900" max="2200"')+field('Días asignados exactos del período','assigned',b.assigned,'number','required min="0" step="0.5"')+field('Ajuste adicional (+ o −)','adjustment',b.adjustment,'number','required step="0.5"')+field('Motivo y observación','reason',b.reason,'text','required')+'<p class="help full">Usá esta opción si conocés el total original del período: se restarán todas las vacaciones tomadas y las reservas. Si ya tenés calculados los días que le quedan, usá «Saldo inicial real» para no descontar dos veces. El ajuste reemplaza su valor anterior.</p><p id="annual-opening-warning" class="help full"></p>',async p=>{await api('balances',{...p,employee:e.id});$('#year').value=p.year;});
  const apply=b=>{const f=$('#editor');f.elements.assigned.value=b.assigned;f.elements.adjustment.value=b.adjustment;f.elements.reason.value=b.reason;$('#annual-opening-warning').textContent=b.opening?'Este período usa un saldo inicial real: editar la asignación anual conserva el dato pero no modifica el saldo disponible. Para cambiarlo, editá el saldo inicial.':'';};apply(b);balanceYearLoader(e,apply);
}
function openingBalanceForm(e,year,b){
  form('Saldo inicial real · '+full(e),field('Año al que corresponden los días','year',year,'number','required min="1900" max="2200"')+field('Días que le quedan al cierre de la fecha de corte','remaining',b.opening?.remaining??'','number','required min="0" step="0.5"')+field('Fecha de corte (inclusive)','cutoff',b.opening?.cutoff??state.today,'date',`required min="${esc(e.hired)}" max="${state.today}"`)+field('Motivo / referencia del saldo','reason',b.opening?.reason??'','text','required')+'<p class="help full">Cargá los días restantes después de las vacaciones tomadas hasta la fecha de corte. No restes las vacaciones futuras aprobadas: Corevia las reservará aparte. El año identifica el período de vacaciones, aunque las fechas de uso correspondan a otro año.</p><p class="opening-note full">Ejemplo: quedan 7 días de 2025 al 31/10/2026. Las vacaciones de ese período tomadas hasta el 31/10 quedan en el historial sin volver a restar. Si un registro atraviesa el corte, solo se descuentan los días desde el 01/11.</p><label class="full check"><input name="confirm" type="checkbox" required>Confirmo que este saldo ya contempla las vacaciones hasta el corte y no descuenta reservas posteriores.</label><p id="opening-preview" class="help full"></p><div class="full"><button type="button" id="clear-opening" class="danger">Volver al cálculo por asignación anual…</button></div>',async p=>{await api('opening-balances',{...p,employee:e.id,confirm:p.confirm==='on'});$('#year').value=p.year;});
  const apply=b=>{const f=$('#editor');f.elements.remaining.value=b.opening?.remaining??'';f.elements.cutoff.value=b.opening?.cutoff??state.today;f.elements.reason.value=b.opening?.reason??'';f.elements.confirm.checked=false;$('#clear-opening').hidden=!b.opening;preview();};
  const preview=()=>{const f=$('#editor'),cutoff=f.elements.cutoff.value,remaining=Number(f.elements.remaining.value),year=Number(f.elements.year.value);let used=0,reserved=0,included=0;for(const a of state.absences.filter(a=>a.employee===e.id&&a.year===year&&a.type==='Vacaciones'&&['Disfrutadas','Aprobadas'].includes(a.state))){const after=iso(new Date(new Date(cutoff+'T12:00:00').getTime()+86400000));const start=a.start>after?a.start:after;const n=Math.max(0,Math.round((new Date(a.end+'T12:00:00Z')-new Date(start+'T12:00:00Z'))/86400000)+1);if(a.state==='Disfrutadas'||a.end<state.today){used+=n;included+=a.days-n;}else reserved+=n;}$('#opening-preview').textContent=cutoff&&f.elements.remaining.value!==''?`Con el historial actual: ${included} días ya incluidos; ${used} utilizados posteriores; ${reserved} reservados. Disponible resultante: ${remaining-used-reserved} días.`:'';};
  apply(b);balanceYearLoader(e,apply);for(const name of ['remaining','cutoff'])$('#editor').elements[name].oninput=preview;
  $('#clear-opening').onclick=()=>{const year=$('#editor').elements.year.value;if(!confirm('¿Volver al cálculo anual? Se restarán todas las vacaciones tomadas del período, incluidas las anteriores al corte. El historial se conserva.'))return;form('Volver al cálculo anual',field('Período anual','year',year,'number','required readonly')+field('Motivo del cambio','reason','','text','required'),async p=>{await api('opening-balances',{...p,employee:e.id,clear:true,confirm:true});$('#year').value=p.year;});};
}
function absenceDetail(id){const a=state.absences.find(a=>a.id===id),e=person(a.employee);modal(full(e),`<p><span class="badge ${a.type==='Vacaciones'?'':'license'}">${esc(a.type)}</span> · ${esc(e.sector)}</p><div class="detail-grid">${[['Inicio',fmt(a.start)],['Finalización',fmt(a.end)],['Días corridos',a.days],['Período anual',a.year],['Estado',a.state],['Solicitud',fmt(a.requested)],['Aprobación',fmt(a.approved)],['Responsable',a.approver||'—'],...(a.cutoff&&a.type==='Vacaciones'?[['Ya incluidos al corte',a.included_days+' días'],['Computables posteriores',a.chargeable_days+' días']]:[])].map(([k,v])=>`<div><small>${k}</small>${esc(v)}</div>`).join('')}</div><p>${esc(a.notes||'Sin observaciones.')}</p>${admin()?'<div class="actions"><button id="cancel-absence" class="danger">Cancelar registro</button><button id="edit-absence" class="primary">Editar</button></div>':''}`);if(admin()){$('#edit-absence').onclick=()=>absenceForm(a);$('#cancel-absence').onclick=async()=>{if(!confirm('¿Cancelar esta ausencia? Se conservará en el historial. Solo se liberarán los días que Corevia estuviera descontando; los días ya incluidos en un saldo inicial no lo modifican.'))return;try{await api('absences',{...a,state:'Canceladas',confirm:true});$('#modal').close();await refresh();notice('Ausencia cancelada.');}catch(err){notice(err.message,true);}};}}
function absenceForm(a={type:'Vacaciones',year:$('#year').value,state:'Solicitadas',requested:state.today},historical=false){
  const employees=state.employees.filter(e=>e.active||historical||e.id===a.employee);
  if(!employees.length){notice('Primero agregá un empleado activo.',true);return;}
  form(a.id?'Editar ausencia':historical?'Registrar vacaciones ya tomadas':'Registrar vacaciones o licencias',
    `<label class="full">¿Qué querés registrar?<select name="entry_mode">${opt('normal','Vacaciones futuras / solicitudes / licencias',!historical)+opt('historical','Vacaciones ya tomadas (hasta hoy)',historical)}</select></label><p class="opening-note full">${historical?'Este modo es solo para vacaciones ya disfrutadas y admite fechas hasta hoy. Para cargar diciembre u otras fechas futuras, elegí «Vacaciones futuras / solicitudes / licencias» arriba; se conservarán los datos que ingresaste.':'Podés seleccionar fechas futuras tanto en Desde como en Hasta. Usá Solicitadas si están pendientes o Aprobadas para reservar días; Disfrutadas corresponde únicamente a vacaciones que ya terminaron.'}</p>`+
    `<label>Empleado<select name="employee">${employees.map(e=>opt(e.id,full(e)+' · '+e.sector,e.id===Number(a.employee))).join('')}</select></label><label>Tipo<select name="type">${state.types.filter(t=>(t.active||t.name===a.type)&&(!historical||t.name==='Vacaciones')).map(t=>opt(t.name,t.name,t.name===a.type)).join('')}</select></label>`+
    field('Período anual','year',a.year,'number','required min="1900" max="2200"')+
    `<label>Estado<select name="state">${(historical?['Disfrutadas']:['Solicitadas','Aprobadas','Disfrutadas','Rechazadas','Canceladas']).map(s=>opt(s,s,s===a.state)).join('')}</select></label>`+
    field('Desde','start',a.start,'date',historical?`required max="${state.today}"`:'required')+
    field('Hasta (inclusive)','end',a.end,'date',historical?`required max="${state.today}"`:'required')+
    '<p id="day-count" class="help full">Días corridos: —</p>'+
    field('Fecha de solicitud','requested',a.requested,'date','required')+field('Fecha de aprobación','approved',a.approved,'date')+field('Responsable de aprobación','approver',a.approver)+
    `<label class="full">Observaciones<textarea name="notes">${esc(a.notes)}</textarea></label><p class="help full">Evitá incluir diagnósticos médicos o información sensible innecesaria.</p>`,
    async p=>{try{await api('absences',{...p,id:a.id,historical});}catch(e){if(e.status===409&&e.data.warnings){if(!confirm(e.data.warnings.join('\n\n')+'\n\n¿Confirmás esta excepción? Quedará registrada.'))throw new Error('Revisá las fechas o el saldo antes de guardar.');await api('absences',{...p,id:a.id,historical,confirm:true});}else throw e;}}
  );
  const f=$('#editor');
  const calc=()=>{
    const start=f.elements.start.value,end=f.elements.end.value;
    f.elements.end.min=start;
    const n=Math.round((new Date(end+'T12:00:00Z')-new Date(start+'T12:00:00Z'))/86400000)+1;
    $('#day-count').textContent='Días corridos: '+(Number.isFinite(n)&&n>0?n:'—')+(historical?' · Si existe saldo inicial para este empleado y período, los días hasta el corte no se descuentan de nuevo. Sin saldo inicial, se descuentan de la asignación anual.':'');
  };
  f.elements.start.onchange=calc;f.elements.end.onchange=calc;calc();
  f.elements.entry_mode.onchange=()=>{
    const values=Object.fromEntries(new FormData(f)),past=values.entry_mode==='historical';
    absenceForm({...a,...values,employee:Number(values.employee),state:past?'Disfrutadas':values.state==='Disfrutadas'?'Solicitadas':values.state,type:past?'Vacaciones':values.type},past);
  };
}
function renderTypes(){$('#types').innerHTML=state.types.map(t=>`<p>${esc(t.name)} ${!t.active?'(inactivo)':''} ${t.name!=='Vacaciones'&&admin()?`<button data-type="${esc(t.name)}">Editar</button>`:''}</p>`).join('');document.querySelectorAll('[data-type]').forEach(b=>b.onclick=()=>typeForm(state.types.find(t=>t.name===b.dataset.type)));}
function typeForm(t={active:1}){form('Tipo de licencia',field('Nombre','name',t.name,'text','required')+`<label>Estado<select name="active">${opt('1','Activo',!!t.active)+opt('0','Inactivo',!t.active)}</select></label>`,p=>api('types',{...p,old:t.name,active:p.active==='1'}));}
function restoreSearchControls(){
  const filters=searches[view];
  $('#search-form').closest('.toolbar').hidden=!filters;
  $('#search-status').hidden=!filters;
  if(!filters)return;
  $('#search').value=filters.query;
  $('#sector').hidden=view==='employees';$('#type').hidden=view==='employees';
  $('#sector').value=filters.sector||'';$('#type').value=filters.type||'';
}
for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>{
  view=b.dataset.view;
  for(const v of ['calendar','employees','absences','settings'])$('#'+v+'-view').hidden=v!==view;
  document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('selected',x===b));
  $('#view-title').textContent={calendar:'Calendario de ausencias',employees:'Tu equipo, en un solo lugar',absences:'Vacaciones y licencias',settings:'Administración del espacio'}[view];
  restoreSearchControls();renderSearchStatus();
};
$('#search-form').onsubmit=e=>{
  e.preventDefault();if(!searches[view])return;
  searches[view].query=$('#search').value.trim().replace(/\s+/g,' ');$('#search').value=searches[view].query;render();
};
$('#clear-search').onclick=()=>{
  if(!searches[view])return;
  searches[view].query='';if(view!=='employees'){searches[view].sector='';searches[view].type='';}else $('#active-filter').value='';
  restoreSearchControls();render();$('#search').focus();
};
$('#search').addEventListener('input',()=>{
  if(!$('#search').value&&searches[view]){searches[view].query='';render();}
});
for(const field of ['sector','type'])$('#'+field).onchange=()=>{if(searches[view]&&view!=='employees'){searches[view][field]=$('#'+field).value;render();}};
for(const selector of ['#active-filter','#sort'])$(selector).addEventListener('change',render);
$('#year').onchange=()=>refresh().catch(e=>notice(e.message,true));
$('#prev').onclick=()=>{shown=new Date(shown.getFullYear(),shown.getMonth()-1,1);renderCalendar();renderSearchStatus();};$('#next').onclick=()=>{shown=new Date(shown.getFullYear(),shown.getMonth()+1,1);renderCalendar();renderSearchStatus();};$('#today').onclick=()=>{shown=new Date();renderCalendar();renderSearchStatus();};$('#month').onchange=e=>{if(e.target.value){shown=new Date(e.target.value+'-01T12:00:00');renderCalendar();renderSearchStatus();}};
$('#new-history').onclick=()=>absenceForm({type:'Vacaciones',year:$('#year').value,state:'Disfrutadas',requested:state.today},true);
$('#new-employee').onclick=()=>employeeForm();$('#new-absence').onclick=()=>absenceForm();$('#export').onclick=()=>location.href='/api/export?year='+$('#year').value;$('#print').onclick=()=>window.print();$('#backup').onclick=()=>location.href='/api/backup';
$('#new-user').onclick=()=>form('Crear usuario',field('Usuario','username','','text','required')+field('Contraseña (mínimo 12 caracteres)','password','','password','required minlength="12"')+`<label>Permisos<select name="role">${opt('lectura','Gerencia · solo lectura')+opt('admin','Administración · acceso completo')}</select></label>`,p=>api('users',p));
$('#new-type').onclick=()=>typeForm();
$('#demo').onclick=async()=>{try{await api('demo',{});await refresh();notice('Demostración cargada. Los empleados ficticios están identificados como DEMO.');}catch(e){notice(e.message,true);}};
$('#clear-demo').onclick=async()=>{if(!confirm('¿Eliminar los empleados DEMO y TODAS sus ausencias y saldos? No afecta a otros empleados.'))return;try{await api('demo',{delete:true,confirm:'ELIMINAR DEMO'});await refresh();notice('Demostración eliminada.');}catch(e){notice(e.message,true);}};
$('#import').onclick=async()=>{const f=$('#import-file').files[0];if(!f){notice('Seleccioná un archivo .xlsx.',true);return;}if(!confirm('¿Importar todos los empleados del archivo? Los identificadores deben ser únicos.'))return;const p=new FormData();p.append('file',f);p.append('skip_existing',$('#import-skip').checked?'1':'0');try{const r=await api('import',p);await refresh();notice(`${r.count} empleados importados; ${r.skipped} existentes omitidos sin cambios.`);}catch(e){notice(e.message,true);}};
$('#restore').onclick=()=>{form('Restaurar copia de seguridad',`<label class="full">Copia .sqlite<input type="file" name="file" accept=".sqlite" required></label>`+field('Escribí RESTAURAR para confirmar','confirm','','text','required pattern="RESTAURAR"')+field('Tu contraseña actual','password','','password','required')+'<p class="help full">Se reemplazarán todos los datos. Los usuarios y contraseñas pasarán a ser los de la copia. Asegurate de conocer una cuenta administradora de esa copia.</p>',async()=>{await api('restore',new FormData($('#editor')));location.reload();});};
$('#audit').onclick=async()=>{try{const logs=await api('audit');modal('Registro de cambios',logs.map(l=>`<div class="history-item"><strong>${esc(l.action)}</strong><small> · ${esc(l.at)} · ${esc(l.actor)}</small><p>${esc(l.detail)}</p></div>`).join('')||'<p>Sin cambios registrados.</p>');}catch(e){notice(e.message,true);}};
init();
