'use strict';
(() => {
  const $ = s => document.querySelector(s);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const demo = document.body.dataset.demo === 'true';
  const labels = {draft:'Utkast',ready:'Klar för utskick',sending:'Utskick pågår / behöver kontrolleras',sent:'Överlämnat till mejltjänsten',simulated:'Simulerat utskick',failed:'Utskick misslyckades',uncertain:'Okänd leveransstatus'};
  let token='', reports=[], messages=[], current=null, currentReport=null, mailConfigured=false, lookupEnabled=false, loading=false;
  let activeRequest=0;
  async function api(path,options={}) {
    const headers={'X-CSRF-Token':token};
    if(options.body){headers['Content-Type']='application/json';options.body=JSON.stringify(options.body);}
    const response=await fetch(path,{...options,headers,credentials:'same-origin'});
    const data=await response.json();
    if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Åtgärden kunde inte genomföras.');
    return data;
  }
  const reportPath=id=>'/api/admin/reports/'+encodeURIComponent(id);
  const reviewOK=r=>r && r.review_checked && !['new','rejected','archived'].includes(r.status);
  function demoVariants(r) {
    const concerns={air:'mycket tomrum',filler:'mycket fyllnadsmaterial',oversized:'en stor låda i förhållande till innehållet',protection:'frågor om produktskyddet',other:'förpackningens utformning'};
    const observation=r.issues.map(x=>concerns[x]).join(', ');
    const openings=[`Via Noair, ett initiativ av Boxon, har vi fått en observation om ${observation} i en leverans från ${r.company}.`,`Vi på Boxon vill gärna prata med er om förpackningar. En observation via Noair om en leverans från ${r.company} rör ${observation}.`,`Kan en mer anpassad förpackning vara intressant för ${r.company}? Via Noair har vi fått en observation som rör ${observation}.`];
    const terms=['laddare','skor','kläder','glas','papper','plast','luft'].filter(term=>new RegExp('\\b'+term+'\\b','i').test(r.comment||''));
    return openings.map(opening=>({subject:`En fråga om förpackningar hos ${r.company}`,body:`Hej!\n\n${opening}${r.category?' Rapporten gäller produktkategorin '+r.category+'.':''}${terms.length?' I beskrivningen nämns '+terms.slice(0,3).join(', ')+'.':''}\n\nDet är en enskild kundobservation, inte en fullständig bedömning av er förpackningslösning. Vi vill gärna förstå era krav på produktskydd och packning och undersöka om en mer anpassad lösning kan vara relevant.\n\nÄr du rätt person att prata med om inköp av emballage, eller kan du hänvisa oss vidare? Har ni möjlighet till ett kort samtal?\n\nVänliga hälsningar,\nMarcus Gustafsson, Boxon`}));
  }
  function syncDemo(){
    messages=messages.filter(m=>reports.some(r=>r.id===m.report_id));
    reports.forEach(r=>{
      let m=messages.find(x=>x.report_id===r.id);
      if(!m){const variants=demoVariants(r);m={report_id:r.id,...variants[0],variants,state:'draft',version:1,recipient_name:'',recipient_role:'',recipient_email:'',source_url:'',contact_checked:false,content_checked:false,contacts:[],lookup_note:'Demo: kontaktsökningen använder bara fiktiva exempel.',error:''};messages.push(m);}
      m.company=r.company;
      if(!reviewOK(r)&&['draft','ready','failed'].includes(m.state)){m.state='draft';m.content_checked=false;}
    });
  }
  async function loadQueue(){
    if(loading)return;loading=true;
    try{
      if(demo)syncDemo();
      else{const data=await api('/api/admin/outreach');messages=data.messages;mailConfigured=data.mail_configured;lookupEnabled=data.lookup_enabled;}
      renderQueue();$('#outreach-queue-error').textContent='';
    }catch(e){$('#outreach-queue-error').textContent=e.message;}
    finally{loading=false;}
  }
  function renderQueue(){
    $('#outreach-connection').textContent=demo?'Demoläge: utkast, kontaktförslag och utskick simuleras i sidans minne. Inga mejl skickas.':(mailConfigured?'Mejltjänsten är ansluten. Utskick sker endast när du klickar på Skicka.':'eMarketeer ansluts senare. Utkast och kö kan användas nu, men verkliga utskick är avstängda.');
    const filter=$('#outreach-filter').value;
    const shown=messages.filter(m=>filter==='all'||(filter==='ready'?m.state==='ready':filter==='sent'?['sent','simulated'].includes(m.state):!['sent','simulated'].includes(m.state)));
    $('#outreach-queue-list').innerHTML=shown.length?shown.map(m=>`<article class="outreach-queue-item"><div><span class="outreach-state ${esc(m.state)}">${esc(labels[m.state]||m.state)}</span><h3>${esc(m.company)}</h3><p>${esc(m.subject)}</p><p class="micro">${esc(m.recipient_name||'Ingen kontaktperson vald')} · ${esc(m.recipient_email||'Mottagaradress saknas')}</p>${m.error?`<p class="form-error">${esc(m.error)}</p>`:''}</div><div class="outreach-row-actions"><button class="button outline small" type="button" data-outreach-edit="${esc(m.report_id)}">${['sent','simulated'].includes(m.state)?'Visa meddelande':'Öppna / redigera'}</button>${m.state==='ready'?`<button class="button dark small" type="button" data-outreach-send="${esc(m.report_id)}"${!demo&&!mailConfigured?' disabled':''}>${demo?'Simulera utskick':'Skicka'}</button>`:''}</div></article>`).join(''):'<p class="outreach-empty">Inga meddelanden i den här vyn.</p>';
    document.querySelectorAll('[data-outreach-edit]').forEach(b=>b.addEventListener('click',()=>openEditor(b.dataset.outreachEdit)));
    document.querySelectorAll('[data-outreach-send]').forEach(b=>b.addEventListener('click',()=>send(b.dataset.outreachSend,b)));
  }
  document.addEventListener('noair:dashboard',event=>{token=event.detail.csrf;reports=event.detail.reports;loadQueue();});
  document.addEventListener('noair:outreach-open',event=>openEditor(event.detail.report.id,event.detail.report));
  $('#refresh-outreach').addEventListener('click',loadQueue);
  $('#outreach-filter').addEventListener('change',renderQueue);
  async function openEditor(id,report){
    const request=++activeRequest;
    try{
      const r=report || (demo?reports.find(x=>x.id===id):await api(reportPath(id)));
      const m=demo?messages.find(x=>x.report_id===id):await api(reportPath(id)+'/outreach');
      if(request!==activeRequest)return;
      if(!m)throw Error('Utkastet saknas. Uppdatera kön.');
      current=structuredClone(m);currentReport=r;
      $('#outreach-report-label').textContent=r.company+' · '+r.id;
      $('#outreach-evidence-text').textContent=r.comment||'Ingen beskrivning lämnad. Granska bilderna i rapportvyn.';
      const mapping={name:'recipient_name',role:'recipient_role',email:'recipient_email',source:'source_url',subject:'subject',body:'body'};
      Object.entries(mapping).forEach(([field,key])=>$('#outreach-'+field).value=m[key]||'');
      $('#outreach-contact-checked').checked=m.contact_checked;$('#outreach-content-checked').checked=m.content_checked;
      $('#outreach-log-checked').checked=false;
      $('#outreach-editor-error').textContent='';
      $('#outreach-delivery-state').textContent=(labels[m.state]||m.state)+(m.error?' – '+m.error:'');
      const locked=['sending','sent','uncertain','simulated'].includes(m.state);
      $('#outreach-form').querySelectorAll('input,textarea,select,button').forEach(el=>el.disabled=locked);
      $('#outreach-resolve').hidden=!['sending','uncertain'].includes(m.state);
      $('#outreach-resolve').querySelectorAll('input,button').forEach(el=>el.disabled=false);
      $('#ready-outreach').disabled=locked||!reviewOK(r);
      $('#lookup-outreach-contacts').disabled=locked||(!demo&&!lookupEnabled);
      if(!reviewOK(r)&&!locked)$('#outreach-delivery-state').textContent='Spara som utkast nu. Granska rapporten och spara granskningsrutan i rapportvyn innan meddelandet läggs i utskickskön.';
      renderContacts();
      if(!$('#outreach-dialog').open)$('#outreach-dialog').showModal();
      document.body.style.overflow='hidden';
    }catch(e){$('#outreach-queue-error').textContent=e.message;}
  }
  function renderContacts(){
    $('#outreach-lookup-note').textContent=current.lookup_note||(!demo&&!lookupEnabled?'Automatisk kontaktsökning är avstängd på servern. Lägg till en verifierad kontakt manuellt.':'Sökningen hämtar endast offentliga uppgifter från företagets webbplats.');
    $('#outreach-candidates').innerHTML=(current.contacts||[]).map((c,i)=>`<div class="outreach-candidate"><strong>${esc(c.email)}</strong>${c.context?`<p>${esc(c.context)}</p>`:''}<p class="micro">${c.priority?'Källtexten nämner inköp/förpackning. Ansvar behöver verifieras.':'Offentlig kontakt. Inköpsansvar är inte verifierat.'} · ${esc(c.checked_at||'')}</p>${/^https:\/\//.test(c.source)?`<a href="${esc(c.source)}" target="_blank" rel="noopener noreferrer">Öppna källan ↗</a>`:''}<button class="button outline small" type="button" data-use-contact="${i}"${['sent','sending','uncertain','simulated'].includes(current.state)?' disabled':''}>Använd kontakt</button></div>`).join('');
    document.querySelectorAll('[data-use-contact]').forEach(b=>b.addEventListener('click',()=>{const c=current.contacts[Number(b.dataset.useContact)];$('#outreach-email').value=c.email;$('#outreach-name').value=c.name||'';$('#outreach-role').value=c.role||'';$('#outreach-source').value=c.source;$('#outreach-contact-checked').checked=false;}));
  }
  $('#lookup-outreach-contacts').addEventListener('click',async()=>{
    const button=$('#lookup-outreach-contacts');button.disabled=true;$('#outreach-lookup-note').textContent='Söker efter offentliga kontaktuppgifter…';
    try{
      if(demo){current.contacts=[{email:'inkop@exempelbutik.example',name:'',role:'',source:'https://exempelbutik.example/kontakt',context:'Fiktivt exempel: kontakta oss om emballage och inköp.',priority:true,checked_at:new Date().toISOString().slice(0,10)}];current.lookup_note='Fiktiva demouppgifter. Ingen webbplats har kontaktats.';}
      else{await api(reportPath(current.report_id)+'/contacts',{method:'POST',body:{}});const fresh=await api(reportPath(current.report_id)+'/outreach');current.contacts=fresh.contacts;current.lookup_note=fresh.lookup_note;}
      renderContacts();
    }catch(e){$('#outreach-editor-error').textContent=e.message;}
    finally{button.disabled=false;}
  });
  $('#vary-outreach').addEventListener('click',()=>{const v=current.variants[Number($('#outreach-variant').value)];$('#outreach-subject').value=v.subject;$('#outreach-body').value=v.body;$('#outreach-content-checked').checked=false;});
  ['name','role','email','source'].forEach(id=>$('#outreach-'+id).addEventListener('input',()=>$('#outreach-contact-checked').checked=false));
  ['body','subject'].forEach(id=>$('#outreach-'+id).addEventListener('input',()=>$('#outreach-content-checked').checked=false));
  async function save(state){
    if(!$('#outreach-form').reportValidity())return;
    const button=state==='ready'?$('#ready-outreach'):$('#save-outreach-draft');button.disabled=true;
    try{
      const data={version:current.version,state,contact_checked:$('#outreach-contact-checked').checked,content_checked:$('#outreach-content-checked').checked};
      const mapping={name:'recipient_name',role:'recipient_role',email:'recipient_email',source:'source_url',subject:'subject',body:'body'};
      Object.entries(mapping).forEach(([field,key])=>data[key]=$('#outreach-'+field).value.trim());
      if(state==='ready'&&(!reviewOK(currentReport)||!data.contact_checked||!data.content_checked||!data.recipient_email||!data.subject||!data.body))throw Error('Granska rapporten, kontrollera kontakt och mejltext och fyll i mottagare, ämne och meddelande.');
      if(demo){if(!['draft','ready','failed'].includes(current.state))throw Error('Meddelandet kan inte redigeras.');Object.assign(messages.find(m=>m.report_id===current.report_id),data,{version:current.version+1,contacts:current.contacts,lookup_note:current.lookup_note});}
      else await api(reportPath(current.report_id)+'/outreach',{method:'PUT',body:data});
      $('#outreach-dialog').close();await loadQueue();
    }catch(e){$('#outreach-editor-error').textContent=e.message;}
    finally{button.disabled=false;}
  }
  $('#outreach-form').addEventListener('submit',e=>{e.preventDefault();save('ready');});
  $('#save-outreach-draft').addEventListener('click',()=>save('draft'));
  async function send(id,button){
    button.disabled=true;
    try{
      const m=messages.find(x=>x.report_id===id);
      if(demo){if(m.state!=='ready'||!reviewOK(reports.find(r=>r.id===id)))throw Error('Meddelandet behöver vara granskat och klart.');m.state='simulated';m.version++;}
      else{await api(reportPath(id)+'/outreach/send',{method:'POST',body:{version:m.version}});}
      await loadQueue();
    }catch(e){$('#outreach-queue-error').textContent=e.message;button.disabled=false;}
  }
  document.querySelectorAll('[data-resolve]').forEach(b=>b.addEventListener('click',async()=>{
    try{
      await api(reportPath(current.report_id)+'/outreach/resolve',{method:'POST',body:{version:current.version,state:b.dataset.resolve,checked_provider_log:$('#outreach-log-checked').checked}});
      $('#outreach-dialog').close();await loadQueue();
    }catch(e){$('#outreach-editor-error').textContent=e.message;}
  }));
})();
