'use strict';
(() => {
  const $ = (s, p = document) => p.querySelector(s);
  const $$ = (s, p = document) => [...p.querySelectorAll(s)];
  const demo = document.body.dataset.demo === 'true';
  const issues = {air:'F\u00f6r mycket luft', filler:'Mycket fyllnadsmaterial', oversized:'On\u00f6digt stor l\u00e5da', protection:'Otillr\u00e4ckligt skydd', other:'Annat'};
  const statuses = {new:'Ny', reviewed:'Granskad', opportunity:'Att kontakta', contacted:'Kontaktad', meeting:'M\u00f6te bokat', archived:'Arkiverad', rejected:'Avvisad'};
  let csrf = '', settings = {}, authenticated = false, allReports = [], selected = [], receipt = null;
  let objectURLs = [], receiptDownloaded = false, submitting = false;
  let photoQueue = Promise.resolve();
  const sessionReady = Promise.resolve().then(initialize);
  const escape = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const nowISO = () => new Date().toISOString();
  const text = (s,v) => { $(s).textContent = v; };
  const key = r => { try { return r.website ? new URL(r.website).hostname.replace(/^www\./,'') : r.company.trim().toLocaleLowerCase('sv'); } catch { return r.company.trim().toLocaleLowerCase('sv'); } };
  const date = s => new Date(s).toLocaleDateString('sv-SE');
  const badge = s => `<span class="status-badge ${escape(s)}">${escape(statuses[s] || s)}</span>`;
  function toast(message) { text('#toast', message); $('#toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('#toast').hidden = true, 4200); }
  function saveFile(content, type, name) { const url=URL.createObjectURL(new Blob([content], {type})); const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
  function showDialog(dialog) { if (!dialog.open) dialog.showModal(); document.body.style.overflow='hidden'; }
  function closeDialog(dialog) { dialog.close(); if (!document.querySelector('dialog[open]')) document.body.style.overflow=''; }
  $$('[data-close]').forEach(b => b.addEventListener('click', () => closeDialog(b.closest('dialog'))));
  $$('dialog').forEach(d => { d.addEventListener('close', () => {if (!document.querySelector('dialog[open]')) document.body.style.overflow='';}); d.addEventListener('click', e => { if(e.target === d) {const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeDialog(d);} }); });
  async function api(path, options={}) {
    const headers = new Headers(options.headers || {});
    if(options.method && options.method !== 'GET') headers.set('X-CSRF-Token', csrf);
    if(options.body && !(options.body instanceof FormData)) { headers.set('Content-Type','application/json'); options.body=JSON.stringify(options.body); }
    const response = await fetch(path, {...options, headers, credentials:'same-origin'});
    let data; try { data=await response.json(); } catch { throw new Error('Servern kunde inte svara. Prova igen.'); }
    if (!response.ok) throw new Error(typeof data.detail==='string' ? data.detail : 'N\u00e5got gick fel. Kontrollera uppgifterna och prova igen.');
    return data;
  }
  async function initialize() {
    try {
      if(demo) {
        $('#preview-bar').hidden=false; $('#wizard-demo-note').hidden=false; $('#admin-demo-note').hidden=false; authenticated=true;
        settings={mode:'demo',retention_days:180};
        const d=nowISO();
        allReports=[
          {id:'DEMO-001',company:'Exempelbutik A',website:'https://butik-a.example',category:'Elektronik',issues:['air','oversized'],comment:'Fiktivt exempel: En liten laddare i en l\u00e5da som var betydligt st\u00f6rre \u00e4n produkten.',created_at:d,status:'new',notes:'',review_checked:false,images:[],email:'',contact_permission:false},
          {id:'DEMO-002',company:'Exempelbutik B',website:'https://butik-b.example',category:'Hem & inredning',issues:['filler'],comment:'Fiktivt exempel: Mycket fyllnadsmaterial runt en liten produkt.',created_at:d,status:'reviewed',notes:'Kontrollera skyddsbehovet med f\u00f6retaget.',review_checked:true,images:[],email:'',contact_permission:false},
          {id:'DEMO-003',company:'Exempelbutik C',website:'https://butik-c.example',category:'Sport & fritid',issues:['oversized'],comment:'Fiktivt exempel: Produkten hade gott om plats i kartongen.',created_at:d,status:'contacted',notes:'Exempel p\u00e5 uppf\u00f6ljning, inte en verklig kontakt.',review_checked:true,images:[],email:'',contact_permission:false}
        ];
      } else {
        const data=await api('/api/session');csrf=data.csrf;settings=data.settings;authenticated=data.authenticated;
        if(settings.mode!=='production') {$('#local-banner').hidden=false;text('#local-banner','Lokal testversion. Anv\u00e4nd endast fiktiva uppgifter och testbilder.');}
        else if(!settings.submissions_enabled) {$('#local-banner').hidden=false;text('#local-banner','Noair f\u00f6rbereds f\u00f6r lansering. Rapporteringen \u00e4r inte \u00f6ppen \u00e4nnu.');}
      }
      renderPrivacy();
      if(document.body.dataset.page==='admin') await loadDashboard();
    } catch(error) { toast('F\u00f6rbindelsen kunde inte startas. Ladda om sidan f\u00f6r att prova igen.'); text('#login-error',error.message); }
  }
  $$('[data-view]').forEach(b => b.addEventListener('click', async () => { document.body.dataset.page=b.dataset.view;$$('[data-view]').forEach(x=>x.classList.toggle('active',x===b));if(b.dataset.view==='admin')await loadDashboard();window.scrollTo(0,0); }));
  if(demo) $('.admin-header .logo').addEventListener('click',e=>{e.preventDefault();$('[data-view="public"]').click();});
  if(demo) $('#admin-footer-link').addEventListener('click',e=>{e.preventDefault();$('[data-view="admin"]').click();});

  const scrollToReport = () => $('#report-dialog').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
  $$('[data-open-report]').forEach(b => b.addEventListener('click', async () => {
    await sessionReady;
    scrollToReport();
  }));
  function clearValidation() {
    $$('.field-error').forEach(el=>el.remove());
    $$('#report-form [aria-invalid]').forEach(el=>el.removeAttribute('aria-invalid'));
    $$('#report-form [aria-describedby]').forEach(el=>{
      const ids=el.getAttribute('aria-describedby').split(/\s+/).filter(id=>!id.startsWith('validation-'));
      if(ids.length)el.setAttribute('aria-describedby',ids.join(' '));else el.removeAttribute('aria-describedby');
    });
    text('#report-error','');
  }
  function resetReport() {
    $('#report-form').reset();selected=[];objectURLs.forEach(URL.revokeObjectURL);objectURLs=[];renderPhotos();
    receipt=null;receiptDownloaded=false;$('#report-success').hidden=true;$('#report-form').hidden=false;
    $('.na-card-heading').hidden=false;clearValidation();text('#photo-error','');
  }
  $('#new-report').addEventListener('click',()=>{resetReport();scrollToReport();});
  function failField(selector,message) {
    const error=new Error(message);error.field=selector;throw error;
  }
  function presentError(error) {
    text('#report-error',error.message);
    const field=error.field?$(error.field):null;
    if(field) {
      field.setAttribute('aria-invalid','true');
      const id='validation-'+(field.id||'issues');
      const note=document.createElement('p');note.id=id;note.className='field-error form-error';note.textContent=error.message;
      const group=field.closest('.check-label')||field;
      group.insertAdjacentElement('afterend',note);
      field.setAttribute('aria-describedby',[field.getAttribute('aria-describedby')||'',id].filter(Boolean).join(' '));
      if(field.closest('details'))field.closest('details').open=true;
      if(!['INPUT','SELECT','TEXTAREA','BUTTON'].includes(field.tagName))field.setAttribute('tabindex','-1');
      field.focus({preventScroll:true});field.scrollIntoView({behavior:'auto',block:'center'});
    }else{
      $('#report-error').focus({preventScroll:true});$('#report-error').scrollIntoView({behavior:'auto',block:'center'});
    }
  }
  function normalizeWebsite(input) {
    if(!input.trim())return '';
    const u=new URL(/^https?:\/\//i.test(input.trim())?input.trim():'https://'+input.trim());
    if(!['https:','http:'].includes(u.protocol)||!u.hostname.includes('.')||u.username||u.password||u.port)throw new Error('Ange en giltig webbplats, till exempel butik.se.');
    return 'https://'+u.hostname.toLowerCase();
  }

  function validateForm() {
    clearValidation();
    if(!selected.length)failField('#upload-zone','V\u00e4lj minst en bild innan du skickar rapporten.');
    if(!$('#company').value.trim())failField('#company','Ange butikens namn.');
    try{normalizeWebsite($('#website').value);}catch{failField('#website','Ange en giltig webbplats, till exempel butik.se.');}
    if(!$('input[name="issues"]:checked'))failField('.issue-field','V\u00e4lj minst en sak du reagerade p\u00e5.');
    if(!$('#privacy-confirmed').checked)failField('#privacy-confirmed','Kontrollera bilderna och bekr\u00e4fta att du l\u00e4st informationen.');
    if($('#email').value.trim() && !$('#email').checkValidity())failField('#email','Ange en giltig e-postadress, eller l\u00e4mna f\u00e4ltet tomt.');
    if($('#email').value.trim() && !$('#contact-permission').checked)failField('#contact-permission','Godk\u00e4nn kontakt om rapporten, eller l\u00e4mna e-postf\u00e4ltet tomt.');
    if($('#contact-permission').checked && !$('#email').value.trim())failField('#email','Ange din e-postadress eller avmarkera kontaktalternativet.');
  }
  async function addPhotos(files) {
    text('#photo-error','');
    for(const file of files) {
      if(selected.length>=3){text('#photo-error','Du kan ladda upp h\u00f6gst tre bilder.');break;}
      if(!['image/jpeg','image/png','image/webp'].includes(file.type)){text('#photo-error','V\u00e4lj JPG, PNG eller WebP. HEIC beh\u00f6ver f\u00f6rst konverteras till JPG.');continue;}
      if(file.size>8*1024*1024){text('#photo-error','Varje bild f\u00e5r vara h\u00f6gst 8 MB.');continue;}
      const url=URL.createObjectURL(file);
      try {
        const image=new Image();image.src=url;await image.decode();
        if(image.naturalWidth*image.naturalHeight>25000000)throw new Error('Bilden har f\u00f6r h\u00f6g uppl\u00f6sning. V\u00e4lj en mindre version.');
        selected.push(file);objectURLs.push(url);
      } catch(e){URL.revokeObjectURL(url);text('#photo-error',e.message.startsWith('Bilden')?e.message:'En av bilderna kunde inte l\u00e4sas.');}
    }
    renderPhotos();$('#photos').value='';
  }
  function renderPhotos() {const p=$('#photo-previews');p.replaceChildren();selected.forEach((file,i)=>{const box=document.createElement('div');box.className='photo-preview';const img=document.createElement('img');img.src=objectURLs[i];img.alt='Vald bild '+(i+1);const b=document.createElement('button');b.type='button';b.textContent='\u00d7';b.setAttribute('aria-label','Ta bort bild '+(i+1));b.addEventListener('click',()=>{URL.revokeObjectURL(objectURLs[i]);objectURLs.splice(i,1);selected.splice(i,1);renderPhotos();});box.append(img,b);p.append(box);});}
  function queuePhotos(files) { photoQueue=photoQueue.then(()=>addPhotos(files)).catch(()=>text('#photo-error','Bilderna kunde inte behandlas. Prova igen.')); }
  $('#photos').addEventListener('change',e=>queuePhotos([...e.target.files]));
  const zone=$('#upload-zone');zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('dragging');});zone.addEventListener('dragleave',()=>zone.classList.remove('dragging'));zone.addEventListener('drop',e=>{e.preventDefault();zone.classList.remove('dragging');queuePhotos([...e.dataTransfer.files]);});
  $('#report-form').addEventListener('submit',async e=>{
    e.preventDefault();if(submitting)return;
    submitting=true;$('#submit-report').disabled=true;
    try{
      await photoQueue;await sessionReady;validateForm();text('#report-error','');
      const form=new FormData(e.target);form.set('website',normalizeWebsite($('#website').value));form.set('privacy_confirmed',$('#privacy-confirmed').checked?'true':'false');form.set('contact_permission',$('#contact-permission').checked?'true':'false');selected.forEach(f=>form.append('photos',f));
      if(demo){
        const id='DEMO-'+crypto.getRandomValues(new Uint32Array(1))[0].toString(16).toUpperCase().slice(0,8);const deletion_token=Array.from(crypto.getRandomValues(new Uint8Array(16))).map(v=>v.toString(16).padStart(2,'0')).join('');
        const images=await Promise.all(selected.map(f=>new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(f);})));
        allReports.unshift({id,company:form.get('company').trim(),website:form.get('website'),issues:form.getAll('issues'),category:form.get('category'),comment:form.get('comment').trim(),email:form.get('email').trim(),contact_permission:form.get('contact_permission')==='true',status:'new',notes:'',review_checked:false,created_at:nowISO(),images,deletion_token});
        receipt={id,deletion_token};
      }else{await sessionReady;receipt=await api('/api/reports',{method:'POST',body:form});}
      text('#receipt-id',receipt.id);text('#success-message',demo?'Din testrapport syns nu i Boxons demo\u00f6versikt. Inget har skickats till Boxon eller sparats p\u00e5 en server.':'Din rapport har tagits emot. Boxon kan anv\u00e4nda den som underlag f\u00f6r en dialog om b\u00e4ttre f\u00f6rpackningar. Vi kan inte lova att alla rapporter leder till kontakt eller f\u00f6r\u00e4ndring.');
      $('#report-form').hidden=true;$('.na-card-heading').hidden=true;$('#report-success').hidden=false;$('#report-success').focus({preventScroll:true});scrollToReport();
    }catch(error){presentError(error);}finally{submitting=false;$('#submit-report').disabled=false;}
  });
  $('#save-receipt').addEventListener('click',()=>{if(!receipt)return;saveFile(`NOAIR ${demo?'DEMOKVITTO':'KVITTO'}\n\nRapport: ${receipt.id}\nPrivat raderingskod: ${receipt.deletion_token}\n\nSpara koden privat. P\u00e5 Noair, v\u00e4lj "Ta bort min rapport".\n${demo?'Demodata finns endast kvar tills sidan laddas om.':'Koden ger m\u00f6jlighet att radera rapporten utan konto.'}\n`,'text/plain;charset=utf-8',`noair-${receipt.id}-kvitto.txt`);receiptDownloaded=true;});
  function renderPrivacy(){
    if(demo||settings.mode!=='production'||!settings.privacy_ready){$('#privacy-content').innerHTML=`<p class="policy-draft"><strong>Utkast f\u00f6r f\u00f6rhandsvisning.</strong> Ansvarigt bolag, r\u00e4ttslig grund, kontaktv\u00e4g, leverant\u00f6rer och lagringstid ska fastst\u00e4llas av Boxon innan verkliga rapporter tas emot.</p><h3>Vad Noair \u00e4r t\u00e4nkt att samla in</h3><p>Bilder, butikens namn, eventuell webbplats, valda problem, eventuell produktkategori och din kommentar. Namn och adress efterfr\u00e5gas inte. E-post \u00e4r frivillig och anv\u00e4nds endast f\u00f6r fr\u00e5gor om rapporten om du godk\u00e4nner det.</p><h3>Varf\u00f6r uppgifterna samlas in</h3><p>Boxon ska granska f\u00f6rpackningar och identifiera m\u00f6jligheter till f\u00f6rb\u00e4ttring. Det kan leda till kommersiell kontakt med butiken. Rapporterna ska inte publiceras, och personuppgifter ska inte skickas vidare till butiken.</p><h3>I den h\u00e4r versionen</h3><p>${demo?'Testrapporter och bilder stannar i sidans arbetsminne. De skickas inte n\u00e5gonstans och f\u00f6rsvinner n\u00e4r sidan laddas om.':'Detta \u00e4r en lokal testinstallation. Anv\u00e4nd endast fiktiva uppgifter. Uppgifter som skickas lagras i den lokala databasen och i den privata bildmappen.'}</p><h3>Cookies och sp\u00e5rning</h3><p>Ingen reklamsp\u00e5rning eller analyskod finns inbyggd. Serverversionen anv\u00e4nder en n\u00f6dv\u00e4ndig sessionscookie f\u00f6r s\u00e4kerhet och inloggning.</p><h3>Radering</h3><p>Du f\u00e5r en privat kod f\u00f6r att radera rapporten. En kompletterande kontaktv\u00e4g f\u00f6r dataskyddsfr\u00e5gor ska vara p\u00e5 plats f\u00f6re lansering.</p>`;}
    else{$('#privacy-content').innerHTML=`<p>Version ${escape(settings.privacy_version)}</p><h3>Vem ansvarar?</h3><p>${escape(settings.controller_name)} ansvarar f\u00f6r behandlingen. Kontakt: ${escape(settings.controller_email)}.</p><h3>Vad vi behandlar och varf\u00f6r</h3><p>Vi tar emot bilder, butiksnamn, valfria butiksadresser p\u00e5 webben, problemval, produktkategori och kommentarer. Syftet \u00e4r att granska f\u00f6rpackningar och identifiera aff\u00e4rsm\u00f6jligheter f\u00f6r Boxon. En rapport kan leda till att Boxon erbjuder butiken f\u00f6rpackningsl\u00f6sningar. E-post \u00e4r frivillig och anv\u00e4nds bara f\u00f6r fr\u00e5gor om rapporten efter ditt separata godk\u00e4nnande.</p><h3>R\u00e4ttslig grund</h3><p>${escape(settings.legal_basis_description)}</p><h3>Vem kan se uppgifterna?</h3><p>Beh\u00f6riga personer hos Boxon och de driftleverant\u00f6rer som beh\u00f6vs f\u00f6r tj\u00e4nsten. Rapporter publiceras inte. Personuppgifter ska inte skickas till butiken.</p><p>${escape(settings.processors_description)}</p><h3>Hur l\u00e4nge?</h3><p>Rapporter, kontaktuppgifter och bilder gallras efter ${escape(settings.retention_days)} dagar, genom automatisk timvis gallring, i den aktiva tj\u00e4nsten. ${escape(settings.backup_policy)}</p><h3>Cookies och s\u00e4kerhetsloggar</h3><p>Tj\u00e4nsten anv\u00e4nder en n\u00f6dv\u00e4ndig sessionscookie, giltig i upp till fyra timmar. Ingen marknadsf\u00f6ringssp\u00e5rning \u00e4r inbyggd. En pseudonymiserad IP-identifierare anv\u00e4nds f\u00f6r att begr\u00e4nsa missbruk och gallras efter ett dygn. ${escape(settings.security_logs_description)}</p><h3>Dina r\u00e4ttigheter</h3><p>Kontakta ${escape(settings.controller_email)} f\u00f6r att beg\u00e4ra tillg\u00e5ng, r\u00e4ttelse, radering eller begr\u00e4nsning, eller f\u00f6r att inv\u00e4nda mot behandlingen. R\u00e4tten till dataportabilitet kan g\u00e4lla beroende p\u00e5 r\u00e4ttslig grund. N\u00e4r behandlingen bygger p\u00e5 samtycke kan du \u00e5terkalla det. Du kan ocks\u00e5 klaga hos Integritetsskyddsmyndigheten (IMY). Inga automatiserade beslut med r\u00e4ttslig effekt fattas om dig.</p><p>Med den privata koden p\u00e5 ditt kvitto kan du ta bort din rapport direkt utan konto. Anv\u00e4nd kontaktv\u00e4gen ovan om du har tappat koden eller om dina uppgifter finns i n\u00e5gon annans rapport.</p>`;}
  }
  $$('[data-privacy]').forEach(b=>b.addEventListener('click',()=>showDialog($('#privacy-dialog'))));
  $$('[data-deletion]').forEach(b=>b.addEventListener('click',()=>{$('#delete-form').hidden=false;$('#delete-success').hidden=true;showDialog($('#delete-dialog'));}));
  $('#delete-form').addEventListener('submit',async e=>{e.preventDefault();text('#delete-error','');try{const id=$('#delete-reference').value.trim();const token=$('#delete-token').value.trim();if(demo){const r=allReports.find(x=>x.id===id&&x.deletion_token===token);if(!r)throw new Error('Rapportnummer eller raderingskod st\u00e4mmer inte.');allReports=allReports.filter(x=>x!==r);renderDashboard();}else{await api('/api/reports/delete',{method:'POST',body:{id,token}});}$('#delete-form').hidden=true;$('#delete-success').hidden=false;}catch(error){text('#delete-error',error.message);}});
  Object.entries(statuses).forEach(([value,label])=>{const o=document.createElement('option');o.value=value;o.textContent=label;$('#status-filter').append(o);});
  async function loadDashboard(){
    $('#login-panel').hidden=authenticated;$('#dashboard').hidden=!authenticated;$('#logout').hidden=!authenticated||demo;
    if(!authenticated)return;
    try{if(!demo)allReports=(await api('/api/admin/reports')).reports;renderDashboard();text('#dashboard-error','');}catch(e){text('#dashboard-error',e.message);}
  }
  function renderDashboard(){
    text('#stat-total',allReports.length);text('#stat-new',allReports.filter(r=>r.status==='new').length);text('#stat-companies',new Set(allReports.map(key)).size);text('#stat-contacted',allReports.filter(r=>['contacted','meeting'].includes(r.status)).length);
    const q=$('#report-search').value.trim().toLocaleLowerCase('sv');const filter=$('#status-filter').value;
    const list=allReports.filter(r=>(!q||[r.company,r.id,r.website].join(' ').toLocaleLowerCase('sv').includes(q))&&(!filter||r.status===filter));
    $('#report-rows').innerHTML=list.map(r=>`<tr><td><strong>${escape(r.company)}</strong><small>${escape(r.website?r.website.replace('https://',''):r.id)}</small></td><td>${r.issues.map(i=>escape(issues[i])).join('<br>')}</td><td>${escape(date(r.created_at))}</td><td>${badge(r.status)}</td><td><button type="button" data-report-id="${escape(r.id)}" aria-label="\u00d6ppna rapport fr\u00e5n ${escape(r.company)}">&nearr;</button></td></tr>`).join('');
    $('#empty-state').hidden=list.length>0;$$('[data-report-id]').forEach(b=>b.addEventListener('click',()=>openReport(b.dataset.reportId)));
  }
  $('#login-form').addEventListener('submit',async e=>{e.preventDefault();text('#login-error','');try{await sessionReady;const data=await api('/api/login',{method:'POST',body:{username:$('#username').value,password:$('#password').value}});csrf=data.csrf;authenticated=true;$('#password').value='';await loadDashboard();}catch(error){text('#login-error',error.message);}});
  $('#logout').addEventListener('click',async()=>{try{const data=await api('/api/logout',{method:'POST',body:{}});csrf=data.csrf;authenticated=false;allReports=[];await loadDashboard();}catch(e){toast(e.message);}});
  $('#refresh-reports').addEventListener('click',()=>loadDashboard());$('#report-search').addEventListener('input',renderDashboard);$('#status-filter').addEventListener('change',renderDashboard);
  $('#export-csv').addEventListener('click',()=>{if(!demo){location.href='/api/admin/export';return;}const clean=v=>'"'+String(v??'').replace(/^[=+@\-\t\r]/,"'$&").replace(/"/g,'""')+'"';const rows=[['Rapport','F\u00f6retag','Webbplats','Datum','Status','Upplevelse'],...allReports.map(r=>[r.id,r.company,r.website,r.created_at,statuses[r.status],r.issues.map(i=>issues[i]).join(', ')])];saveFile('\uFEFF'+rows.map(r=>r.map(clean).join(';')).join('\r\n'),'text/csv;charset=utf-8','noair-demo-oversikt.csv');});
  function outreach(r){return `Hej!\n\nVia Noair, ett initiativ av Boxon, har vi f\u00e5tt in en rapport om utrymmet och packningen i ett paket fr\u00e5n ${r.company}. Underlaget \u00e4r en enskild observation, inte en fullst\u00e4ndig bed\u00f6mning av er f\u00f6rpackningsl\u00f6sning.\n\nVi vill g\u00e4rna f\u00f6rst\u00e5 era krav p\u00e5 produktskydd och packning och unders\u00f6ka om en mer anpassad f\u00f6rpackning kan vara relevant.\n\nHar ni m\u00f6jlighet till ett kort m\u00f6te om detta?\n\nV\u00e4nliga h\u00e4lsningar,\n[Avs\u00e4ndare], Boxon`;}
  async function openReport(id){
    let r=allReports.find(x=>x.id===id);if(!r)return;
    if(!demo){try{r=await api('/api/admin/reports/'+encodeURIComponent(id));}catch(e){toast(e.message);return;}}
    const markup=`<p class="eyebrow">${escape(r.id)} / PRIVAT RAPPORT</p><h2>${escape(r.company)}</h2><p class="detail-meta">${escape(date(r.created_at))} &middot; ${escape(r.category||'Ingen produktkategori')} &middot; ${escape(r.website||'Ingen webbplats angiven')}</p>${r.images.length?`<div class="detail-photos">${r.images.map((src,i)=>`<a href="${escape(src)}" target="_blank" rel="noopener"><img src="${escape(src)}" alt="Rapportbild ${i+1}"></a>`).join('')}</div>`:'<div class="demo-photo">Fiktivt exempel utan kundbild</div>'}<p class="micro">${r.issues.map(i=>escape(issues[i])).join(' &middot; ')}</p><blockquote class="detail-quote">${escape(r.comment||'Ingen kommentar l\u00e4mnad.')}</blockquote>${r.email?`<p class="micro">Kontakt om rapporten: <strong>${escape(r.email)}</strong>. Kontaktgodk\u00e4nnande: ${r.contact_permission?'Ja':'Nej'}.</p>`:''}<div class="detail-fields"><div><label for="detail-status">Status</label><select id="detail-status">${Object.entries(statuses).map(([v,l])=>`<option value="${v}"${v===r.status?' selected':''}>${escape(l)}</option>`).join('')}</select></div><div><label for="detail-notes">Intern anteckning</label><textarea id="detail-notes" maxlength="3000" rows="2" placeholder="N\u00e4sta steg, ansvarig eller CRM-referens. Inga personuppgifter.">${escape(r.notes)}</textarea></div></div><label class="check-label"><input type="checkbox" id="review-checked"${r.review_checked?' checked':''}><span>Jag har granskat underlaget, kontrollerat personuppgifter och bed\u00f6mt att ett sakligt kontaktutkast kan tas fram. Detta godk\u00e4nner inte att bilder skickas vidare.</span></label><p class="form-error" id="detail-error" role="alert"></p><div class="detail-actions"><button class="button dark" id="save-report">Spara \u00e4ndringar</button><button class="button outline" id="show-outreach"${!r.review_checked||['new','rejected'].includes(r.status)?' disabled':''}>Visa kontaktutkast</button><button class="plain-link danger-link" id="admin-delete">Radera rapport</button></div><section id="outreach-panel" hidden><h3 style="margin-top:28px">Kontaktutkast</h3><p class="review-notice">Anpassa och faktagranska innan kontakt. Inget skickas automatiskt. Bifoga inte originalbilder med personuppgifter.</p><div class="outreach-text" id="outreach-text"></div><button class="button outline small" id="copy-outreach" style="margin-top:14px">Kopiera texten</button></section>`;
    $('#detail-content').innerHTML=markup;showDialog($('#detail-dialog'));
    $('#save-report').addEventListener('click',async()=>{text('#detail-error','');try{const changes={status:$('#detail-status').value,notes:$('#detail-notes').value,review_checked:$('#review-checked').checked};if(!changes.review_checked&&!['new','rejected','archived'].includes(changes.status))throw new Error('Granska rapporten och markera kontrollrutan innan statusen \u00e4ndras.');if(!demo)await api('/api/admin/reports/'+encodeURIComponent(id),{method:'PATCH',body:changes});Object.assign(r,changes);const found=allReports.find(x=>x.id===id);Object.assign(found,changes);renderDashboard();$('#show-outreach').disabled=!r.review_checked||['new','rejected'].includes(r.status);$('#outreach-panel').hidden=true;toast('\u00c4ndringarna \u00e4r sparade.');}catch(e){text('#detail-error',e.message);}});
    $('#show-outreach').addEventListener('click',()=>{text('#outreach-text',outreach(r));$('#outreach-panel').hidden=false;});
    $('#copy-outreach').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(outreach(r));toast('Kontaktutkastet \u00e4r kopierat.');}catch{const range=document.createRange();range.selectNodeContents($('#outreach-text'));const selection=getSelection();selection.removeAllRanges();selection.addRange(range);toast('Texten \u00e4r markerad. Kopiera med Ctrl/Cmd+C.');}});
    $('#admin-delete').addEventListener('click',async()=>{if(!confirm('Radera rapporten och dess bilder permanent?'))return;try{if(!demo)await api('/api/admin/reports/'+encodeURIComponent(id),{method:'DELETE'});allReports=allReports.filter(x=>x.id!==id);renderDashboard();closeDialog($('#detail-dialog'));toast('Rapporten har raderats.');}catch(e){text('#detail-error',e.message);}});
  }
  // No analytics, external fonts, public image URLs, or automatic email sends.
})();
