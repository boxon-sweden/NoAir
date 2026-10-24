'use strict';
(() => {
  const $ = s => document.querySelector(s);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const demo = document.body.dataset.demo === 'true';
  const labels = {pending:'Väntar på utskick',draft:'Utkast',ready:'Klar för utskick',sending:'Utskick pågår / behöver kontrolleras',sent:'Överlämnat till mejltjänsten',simulated:'Simulerat utskick',failed:'Utskick misslyckades',uncertain:'Okänd leveransstatus'};
  let token='', reports=[], messages=[], current=null, currentReport=null, mailConfigured=false, lookupEnabled=false, loading=false;
  let activeRequest=0;
  async function api(path,options={}) {
    const headers={'X-CSRF-Token':token};
    if(options.body){headers['Content-Type']='application/json';options.body=JSON.stringify(options.body);}
    const response=await fetch(path,{...options,headers,credentials:'same-origin'});
    let data;try{data=await response.json();}catch{throw Error('Sökservern kunde inte svara. Kontrollera att rapportvyn kör serverversionen.');}
    if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Åtgärden kunde inte genomföras.');
    return data;
  }
  const reportPath=id=>'/api/admin/reports/'+encodeURIComponent(id);
  const reviewOK=r=>r && r.review_checked && !['new','rejected','archived'].includes(r.status);
  function syncDemo(){
    messages=messages.filter(m=>reports.some(r=>r.id===m.report_id));
    reports.forEach(r=>{
      let m=messages.find(x=>x.report_id===r.id);
      if(!m){const variants=window.noairSalesDrafts(r);m={report_id:r.id,...variants[0],variants,state:'draft',version:1,recipient_name:'',recipient_role:'',recipient_email:'',source_url:'',contact_checked:false,content_checked:false,recipients:[],deliveries:{},contacts:[],lookup_note:'Demo: kontaktsökningen använder bara fiktiva exempel.',error:''};messages.push(m);}
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
    $('#outreach-queue-list').innerHTML=shown.length?shown.map(m=>`<article class="outreach-queue-item"><div><span class="outreach-state ${esc(m.state)}">${esc(labels[m.state]||m.state)}</span><h3>${esc(m.company)}</h3><p>${esc(m.subject)}</p><p class="micro">${esc((m.recipients?.length?m.recipients.map(r=>r.email||r.name||'E-post saknas').join(' · '):(m.recipient_email||'Ingen kontaktperson vald')))}</p>${m.error?`<p class="form-error">${esc(m.error)}</p>`:''}</div><div class="outreach-row-actions"><button class="button outline small" type="button" data-outreach-edit="${esc(m.report_id)}">${['sent','simulated'].includes(m.state)?'Visa meddelande':'Öppna / redigera'}</button>${m.state==='ready'?`<button class="button dark small" type="button" data-outreach-send="${esc(m.report_id)}"${!demo&&!mailConfigured?' disabled':''}>${demo?'Simulera utskick':'Skicka'}${m.recipients?.length?' till '+m.recipients.length+' kontakter':''}</button>`:''}</div></article>`).join(''):'<p class="outreach-empty">Inga meddelanden i den här vyn.</p>';
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
      current.recipients=current.recipients?.length?current.recipients:(m.recipient_email?[{name:m.recipient_name||'',role:m.recipient_role||'',email:m.recipient_email,source_url:m.source_url||''}]:[]);
      if(!current.recipients.length)current.recipients=[{name:'',role:'',email:'',source_url:''}];
      current.deliveries=current.deliveries||{};
      $('#outreach-website').value=r.website||'';
      $('#outreach-demo-examples').hidden=!demo;
      $('#outreach-import-text').value='';$('#outreach-import-source').value='';
      renderRecipients();renderSearchLinks();
      $('#outreach-report-label').textContent=r.company+' · '+r.id;
      $('#outreach-evidence-text').textContent=r.comment||'Ingen beskrivning lämnad. Granska bilderna i rapportvyn.';
      $('#outreach-subject').value=m.subject||'';$('#outreach-body').value=m.body||'';
      $('#outreach-contact-checked').checked=m.contact_checked;$('#outreach-content-checked').checked=m.content_checked;
      $('#outreach-log-checked').checked=false;
      $('#outreach-editor-error').textContent='';
      $('#outreach-delivery-state').textContent=(labels[m.state]||m.state)+(m.error?' – '+m.error:'');
      const locked=['sending','sent','uncertain','simulated'].includes(m.state);
      $('#outreach-form').querySelectorAll('input,textarea,select,button').forEach(el=>el.disabled=locked);
      $('#outreach-resolve').hidden=!['sending','uncertain'].includes(m.state);
      $('#outreach-resolve').querySelectorAll('input,button,select').forEach(el=>el.disabled=false);
      $('#ready-outreach').disabled=locked||!reviewOK(r);
      $('#lookup-outreach-contacts').disabled=locked||(!demo&&!lookupEnabled);
      if(!reviewOK(r)&&!locked)$('#outreach-delivery-state').textContent='Spara som utkast nu. Granska rapporten och spara granskningsrutan i rapportvyn innan meddelandet läggs i utskickskön.';
      renderDeliveries();renderContacts();
      if(!$('#outreach-dialog').open)$('#outreach-dialog').showModal();
      document.body.style.overflow='hidden';
    }catch(e){$('#outreach-queue-error').textContent=e.message;}
  }
  const blankRecipient=()=>({name:'',role:'',email:'',source_url:''});
  const nonempty=r=>r.name||r.email||r.role||r.source_url;
  const contactKey=c=>c.email?c.email.trim().toLowerCase():[c.name,c.role,c.source_url||c.source].join('|').toLowerCase();
  const locked=()=>current&&['sent','sending','uncertain','simulated'].includes(current.state);
  const recipient=c=>({name:c.name||'',role:c.role||'',email:c.email||'',source_url:c.source||c.source_url||''});
  function renderRecipients(){
    $('#outreach-recipients').innerHTML=current.recipients.map((r,i)=>`<fieldset class="outreach-recipient"><legend>Kontakt ${i+1}</legend><div class="outreach-fields">${[['name','Kontaktperson'],['role','Roll / ansvar'],['email','E-postadress'],['source_url','Källa (webbadress)']].map(([field,label])=>{const id=i===0?'outreach-'+(field==='source_url'?'source':field):'recipient-'+i+'-'+field;return `<div><label for="${id}">${label}</label><input id="${id}" data-recipient-index="${i}" data-recipient-field="${field}" value="${esc(r[field])}" type="${field==='email'?'email':field==='source_url'?'url':'text'}" maxlength="${field==='email'?254:field==='source_url'?2048:160}"${locked()?' disabled':''}/></div>`;}).join('')}</div><button class="plain-link danger-link" data-remove-recipient="${i}" type="button"${locked()?' disabled':''}>Ta bort kontakt</button></fieldset>`).join('');
    updateCount();
  }
  function updateCount(){
    const chosen=current.recipients.filter(nonempty);const missing=chosen.filter(r=>!r.email).length;
    $('#outreach-selected-count').textContent=chosen.length+' kontaktpersoner valda'+(missing?' · '+missing+' saknar e-postadress':'');
  }
  function renderSearchLinks(){
    const company=currentReport.company;let host='';
    try{host=new URL($('#outreach-website').value).hostname;}catch{}
    const queries=[...(host?[[`Sök kontakter på ${host}`,`site:${host} (kontakt OR inköp OR förpackning)`]]:[]),['Sök inköps- och förpackningsansvariga',`"${company}" (inköpschef OR emballage OR procurement OR packaging)`],['Sök kundcase och nyheter',`"${company}" (kundcase OR nyheter OR "case study") förpackning`]];
    $('#outreach-search-links').innerHTML='<p>Öppna en sökning och kontrollera källorna:</p>'+queries.map(([label,q])=>`<a href="https://www.google.com/search?q=${encodeURIComponent(q)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`).join('');
  }
  function renderContacts(){
    $('#outreach-lookup-note').textContent=current.lookup_note||(!demo&&!lookupEnabled?'Automatisk kontaktsökning är avstängd på servern. Sök via länkarna eller aktivera serverns kontaktsökning.':'Sökningen börjar på företagets webbplats och fortsätter på nätet om en söktjänst är ansluten.');
    $('#outreach-candidates').innerHTML=(current.contacts||[]).map((c,i)=>{const selected=current.recipients.some(r=>nonempty(r)&&contactKey(r)===contactKey(c));const source=c.source||'';return `<div class="outreach-candidate"><label class="check-label"><input type="checkbox" data-contact-select="${i}"${selected?' checked':''}${locked()?' disabled':''}/><span><strong>${esc(c.name||c.email||'Kontaktförslag')}</strong>${c.name&&c.email?' · '+esc(c.email):''}${c.role?' · '+esc(c.role):''}</span></label>${!c.email?'<p class="micro">Ingen offentlig e-post hittad. Komplettera adressen innan utskick.</p>':''}${c.context?`<p>${esc(c.context)}</p>`:''}<p class="micro">${c.origin==='external'?'Extern källa – kontrollera kopplingen till företaget.':c.origin==='imported'?'Kontakttext importerad av dig.':c.origin==='demo'?'Fiktiv testkontakt.':'Företagets webbplats.'} ${c.priority?'Källan nämner inköp/förpackning.':''} Ansvar behöver verifieras. · ${esc(c.checked_at||'')}</p>${(c.sources||[source]).filter(url=>/^https:\/\//.test(url)).map((url,n)=>`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Öppna källa ${n+1} ↗</a>`).join(' · ')}<button class="button outline small" type="button" data-use-contact="${i}"${locked()?' disabled':''}>Använd kontakt</button></div>`;}).join('');
    $('#outreach-select-all').disabled=locked()||!current.contacts?.length;
    $('#outreach-select-none').disabled=locked()||!current.contacts?.length;
    $('#outreach-demo-examples').disabled=locked();$('#outreach-import-contacts').disabled=locked();
    updateCount();
  }
  function chooseContact(c,selected){
    if(locked())return;
    let chosen=current.recipients.filter(nonempty);const key=contactKey(c);
    if(selected&&!chosen.some(r=>contactKey(r)===key))chosen.push(recipient(c));
    if(!selected)chosen=chosen.filter(r=>contactKey(r)!==key);
    if(chosen.length>30)throw Error('Välj högst 30 kontaktpersoner.');
    current.recipients=chosen.length?chosen:[blankRecipient()];
    $('#outreach-contact-checked').checked=false;
  }
  $('#outreach-candidates').addEventListener('change',e=>{
    if(!e.target.matches('[data-contact-select]'))return;
    try{chooseContact(current.contacts[Number(e.target.dataset.contactSelect)],e.target.checked);renderRecipients();renderContacts();}catch(error){$('#outreach-editor-error').textContent=error.message;e.target.checked=false;}
  });
  $('#outreach-candidates').addEventListener('click',e=>{
    const button=e.target.closest('[data-use-contact]');if(!button)return;
    try{chooseContact(current.contacts[Number(button.dataset.useContact)],true);renderRecipients();renderContacts();}catch(error){$('#outreach-editor-error').textContent=error.message;}
  });
  $('#outreach-select-all').addEventListener('click',()=>{
    try{for(const c of current.contacts)chooseContact(c,true);renderRecipients();renderContacts();}catch(error){$('#outreach-editor-error').textContent=error.message;renderRecipients();renderContacts();}
  });
  $('#outreach-select-none').addEventListener('click',()=>{for(const c of current.contacts)chooseContact(c,false);renderRecipients();renderContacts();});
  $('#outreach-recipients').addEventListener('input',e=>{
    const field=e.target.dataset.recipientField;if(!field||locked())return;
    current.recipients[Number(e.target.dataset.recipientIndex)][field]=e.target.value;
    $('#outreach-contact-checked').checked=false;updateCount();
  });
  $('#outreach-recipients').addEventListener('click',e=>{
    const button=e.target.closest('[data-remove-recipient]');if(!button||locked())return;
    current.recipients.splice(Number(button.dataset.removeRecipient),1);if(!current.recipients.length)current.recipients=[blankRecipient()];$('#outreach-contact-checked').checked=false;renderRecipients();renderContacts();
  });
  $('#add-outreach-recipient').addEventListener('click',()=>{
    if(current.recipients.length>=30){$('#outreach-editor-error').textContent='Välj högst 30 kontaktpersoner.';return;}
    current.recipients.push(blankRecipient());$('#outreach-contact-checked').checked=false;renderRecipients();
  });
  $('#outreach-website').addEventListener('input',renderSearchLinks);
  $('#outreach-demo-examples').addEventListener('click',()=>{
    current.contacts=[{name:'Anna Exempel',email:'inkop@exempelbutik.example',role:'Inköp'},{name:'Erik Exempel',email:'logistik@exempelbutik.example',role:'Logistik'},{name:'Kim Exempel',email:'',role:'Förpackningsansvarig'}].map(c=>({...c,source:'https://exempelbutik.example/kontakt',context:'Fiktiv testkontakt, inte en verklig person.',origin:'demo',priority:true,checked_at:new Date().toISOString().slice(0,10)}));
    current.lookup_note='Tre fiktiva testkontakter. Ingen webbplats har kontaktats.';renderContacts();
  });
  $('#outreach-import-contacts').addEventListener('click',()=>{
    try{
      const source=$('#outreach-import-source').value.trim();if(source&&new URL(source).protocol!=='https:')throw Error('Ange en HTTPS-länk till källan.');
      const input=$('#outreach-import-text').value;
      const matches=input.match(/[A-Za-z0-9.!#$%&'*+\/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}/g)||[];
      const emails=[...new Map(matches.map(email=>[email.toLowerCase(),email])).values()].slice(0,30);
      for(const email of emails){if(!(current.contacts||[]).some(c=>c.email.toLowerCase()===email.toLowerCase()))(current.contacts??=[]).push({email,name:'',role:'',source,context:'Offentlig kontakttext som du klistrat in. Kontrollera namn, roll och företag mot källan.',origin:'imported',priority:false,checked_at:new Date().toISOString().slice(0,10)});}
      current.lookup_note=emails.length+' e-postadresser hittades i den inklistrade texten. Ingen automatisk hämtning har gjorts.';renderContacts();
    }catch(e){$('#outreach-editor-error').textContent=e.message;}
  });
  $('#lookup-outreach-contacts').addEventListener('click',async()=>{
    const button=$('#lookup-outreach-contacts');const generation=activeRequest;const id=current.report_id;
    $('#outreach-editor-error').textContent='';renderSearchLinks();
    if(demo){current.lookup_note='Den här rapportvyn körs på GitHub Pages och kan inte hämta andra webbplatser automatiskt. Öppna söklänkarna ovan och lägg in kontakter manuellt eller klistra in offentlig kontakttext. För automatisk webb- och kontaktsökning behövs serverversionen och en söktjänst.';renderContacts();return;}
    button.disabled=true;$('#outreach-lookup-note').textContent='Söker på företagets webbplats och i tillgängliga webbkällor. Det kan ta upp till en minut…';
    try{
      await api(reportPath(id)+'/contacts',{method:'POST',body:{website:$('#outreach-website').value.trim()}});
      const fresh=await api(reportPath(id)+'/outreach');
      if(generation!==activeRequest||current.report_id!==id)return;
      current.contacts=fresh.contacts;current.lookup_note=fresh.lookup_note;renderContacts();
    }catch(e){if(generation===activeRequest){current.lookup_note='Sökningen kunde inte slutföras. '+e.message;$('#outreach-editor-error').textContent=e.message;renderContacts();}}
    finally{if(generation===activeRequest)button.disabled=locked()||!lookupEnabled;}
  });
  function renderDeliveries(){
    const entries=Object.entries(current.deliveries||{});
    $('#outreach-deliveries').innerHTML=entries.map(([email,d])=>`<p>${esc(email)}: ${esc(labels[d.state]||d.state)}</p>`).join('');
    const unknown=entries.filter(([,d])=>(current.state==='sending'?['sending','uncertain','pending']:['sending','uncertain']).includes(d.state));
    $('#outreach-resolve-email').innerHTML=unknown.map(([email])=>`<option value="${esc(email)}">${esc(email)}</option>`).join('');
  }
  $('#vary-outreach').addEventListener('click',()=>{const v=current.variants[Number($('#outreach-variant').value)];$('#outreach-subject').value=v.subject;$('#outreach-body').value=v.body;$('#outreach-content-checked').checked=false;});
  ['body','subject'].forEach(id=>$('#outreach-'+id).addEventListener('input',()=>$('#outreach-content-checked').checked=false));
  async function save(state){
    if(!$('#outreach-form').reportValidity())return;
    const button=state==='ready'?$('#ready-outreach'):$('#save-outreach-draft');button.disabled=true;
    try{
      const data={version:current.version,state,contact_checked:$('#outreach-contact-checked').checked,content_checked:$('#outreach-content-checked').checked};
      data.recipients=current.recipients.filter(nonempty).map(r=>Object.fromEntries(Object.entries(r).map(([k,v])=>[k,v.trim()])));
      const first=data.recipients[0]||blankRecipient();
      Object.assign(data,{recipient_name:first.name,recipient_role:first.role,recipient_email:first.email,source_url:first.source_url,subject:$('#outreach-subject').value.trim(),body:$('#outreach-body').value.trim()});
      if(state==='ready'&&(!reviewOK(currentReport)||!data.contact_checked||!data.content_checked||!data.recipients.length||data.recipients.some(r=>!r.email)||!data.subject||!data.body))throw Error('Granska rapporten, kontrollera kontakt och mejltext och fyll i mottagare, ämne och meddelande.');
      if(demo){if(!['draft','ready','failed'].includes(current.state))throw Error('Meddelandet kan inte redigeras.');Object.assign(messages.find(m=>m.report_id===current.report_id),data,{version:current.version+1,contacts:current.contacts,recipients:data.recipients,lookup_note:current.lookup_note});}
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
      await api(reportPath(current.report_id)+'/outreach/resolve',{method:'POST',body:{version:current.version,state:b.dataset.resolve,checked_provider_log:$('#outreach-log-checked').checked,recipient_email:$('#outreach-resolve-email').value||undefined}});
      $('#outreach-dialog').close();await loadQueue();
    }catch(e){$('#outreach-editor-error').textContent=e.message;}
  }));
})();
