"""Public contact research: company website first, optional Brave web search.

No report images, comments or consumer contact data are sent to the search API.
External contacts need local evidence of association with the target company.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

import outreach

NAME = re.compile(r"[A-ZÅÄÖÉ][a-zåäöéüß]+(?:[-'][A-ZÅÄÖÉa-zåäöéüß]+)?(?: [A-ZÅÄÖÉ][a-zåäöéüß]+(?:[-'][A-ZÅÄÖÉa-zåäöéüß]+)?){1,3}")
TITLE = re.compile(r'(?:inköpschef|inköpsansvarig|förpackningsansvarig|emballageansvarig|logistikchef|logistikansvarig|purchasing manager|procurement manager|packaging manager|head of procurement|supply chain manager|supply chain director)', re.I)
BLOCKS = {'article','section','div','li','p','address'}


class ContactPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]; self.blocks=[]; self.stack=[]; self.text=[]
        self.script=None; self.scripts=[]; self.ignored=0

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in {'script','style'}:
            self.ignored+=1
            if tag=='script' and attrs.get('type')=='application/ld+json':self.script=[]
        if tag=='a':
            href=attrs.get('href','')
            if len(href)<2048:
                self.links.append(href)
                if href.lower().startswith('mailto:'):
                    self.add_text(' '+urllib.parse.unquote(href[7:]).split('?')[0]+' ')
        if tag in BLOCKS and len(self.stack)<32:
            self.stack.append((tag,[]))
        if tag in BLOCKS or tag in {'h1','h2','h3','h4','br'}:self.add_text('\n')

    def add_text(self,text):
        if self.ignored:return
        self.text.append(text)
        for _,parts in self.stack:parts.append(text)

    def handle_data(self,data):
        if self.script is not None:self.script.append(data)
        self.add_text(data)

    def handle_endtag(self,tag):
        if tag in {'script','style'}:
            if tag=='script' and self.script is not None:
                self.scripts.append(''.join(self.script));self.script=None
            self.ignored=max(0,self.ignored-1)
        if tag in BLOCKS:
            for i in range(len(self.stack)-1,-1,-1):
                if self.stack[i][0]==tag:
                    for _,parts in self.stack[i:]:
                        text=' '.join(''.join(parts).split())
                        if text and len(text)<=900:self.blocks.append(text)
                    self.stack=self.stack[:i];break
        if tag in BLOCKS or tag in {'h1','h2','h3','h4','br'}:self.add_text('\n')


def identity(company,website):
    company=' '.join(company.split()).strip()
    host=urllib.parse.urlsplit(website).hostname or ''
    return company,host.removeprefix('www.')


def associated(text,company,host):
    lower=text.casefold()
    # Exact whole company name or its actual website is required in external
    # contact context. A mere target-company mention elsewhere is insufficient.
    return bool((company and re.search(r'(?<!\w)'+re.escape(company.casefold())+r'(?!\w)',lower)) or (host and host in lower))


def candidate(email,name,role,context,url,origin):
    key=email.casefold() if email else (name.casefold()+'|'+role.casefold()+'|'+url)
    return {'id':hashlib.sha256(key.encode()).hexdigest()[:24], 'email':email, 'name':name,
            'role':role, 'context':context[:700], 'source':url, 'origin':origin,
            'priority':bool(outreach.ROLE.search(role+' '+context)),
            'checked_at':time.strftime('%Y-%m-%d',time.gmtime())}


def structured_people(value):
    if isinstance(value,dict):
        types=value.get('@type',[])
        if 'Person' in ([types] if isinstance(types,str) else types):yield value
        for item in value.values():yield from structured_people(item)
    elif isinstance(value,list):
        for item in value:yield from structured_people(item)


def suggested_names(context,company):
    context=TITLE.sub('|',context)
    if company:context=re.sub(re.escape(company),'|',context,flags=re.I)
    return [m.group() for m in NAME.finditer(context) if not outreach.ROLE.search(m.group())]


def extract_contacts(html,url,company,host,external=False):
    page=ContactPage();page.feed(html)
    origin='external' if external else 'website'
    found=[]
    text='\n'.join(page.text)
    emails=set(outreach.EMAIL.findall(text))
    for email in sorted(emails):
        # External-page footers often contain the publisher's contacts. Only
        # accept plaintext emails on the actual target domain. Cross-domain
        # addresses require explicit structured Person/worksFor evidence below.
        email_host=email.rsplit('@',1)[-1].casefold()
        if external and (not host or not (email_host==host.casefold() or email_host.endswith('.'+host.casefold()))):continue
        blocks=[b for b in page.blocks if email in b and (not external or associated(b,company,host))]
        if not blocks and external:continue
        blocks.sort(key=lambda b:(not bool(TITLE.search(b)),len(b)))
        context=blocks[0] if blocks else next((line.strip() for line in text.splitlines() if email in line),'')
        title=TITLE.search(context)
        names=suggested_names(context,company)
        # Text-derived names are suggestions and always carry the source context.
        name=min(names,key=lambda n:abs(context.find(n)-title.start())) if title and names else ''
        found.append(candidate(email,name,title.group() if title else '',context,url,origin))
    # Structured public Person records provide stronger name/role evidence.
    for script in page.scripts:
        try:people=list(structured_people(json.loads(script)))
        except (ValueError,RecursionError,TypeError):continue
        for person in people[:30]:
            name=person.get('name','');role=person.get('jobTitle','')
            if not isinstance(name,str) or not isinstance(role,str) or not name or len(name)>160 or len(role)>160:continue
            employer=person.get('worksFor',{})
            employer=employer.get('name','') if isinstance(employer,dict) else employer
            context=' · '.join(x for x in [name,role,employer] if isinstance(x,str))
            if external and not associated(context,company,host):continue
            email=person.get('email','')
            email=email.removeprefix('mailto:') if isinstance(email,str) else ''
            if email and not outreach.valid_email(email):email=''
            if not role and not email:continue
            found.append(candidate(email,name,role,context,url,origin))
    # Named decision makers may appear in interviews/cases without a public email.
    if external:
        for block in page.blocks:
            if not associated(block,company,host):continue
            title=TITLE.search(block)
            if not title:continue
            names=suggested_names(block,company)
            name=min(names,key=lambda n:abs(block.find(n)-title.start())) if names else ''
            if name and not any(c['name']==name for c in found):
                found.append(candidate('',name,title.group(),block,url,origin))
    return found,page.links


class NoSearchRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None  # Never forward a search credential to a redirected host.


def brave_search(company,website,api_key):
    if not api_key:raise ValueError('Webbsökning är inte ansluten: Brave Search API-nyckel saknas.')
    query=f'"{company}" (inköpschef OR inköpsansvarig OR förpackning OR procurement OR packaging) (kontakt OR kundcase OR nyheter)'
    params=urllib.parse.urlencode({'q':query[:600],'count':8,'search_lang':'sv'})
    request=urllib.request.Request('https://api.search.brave.com/res/v1/web/search?'+params,
        headers={'Accept':'application/json','X-Subscription-Token':api_key})
    try:
        with urllib.request.build_opener(NoSearchRedirect()).open(request,timeout=12) as response:
            raw=response.read(500_001)
        if len(raw)>500_000:raise ValueError('Söktjänstens svar var för stort.')
        data=json.loads(raw)
        if not isinstance(data,dict) or not isinstance(data.get('web',{}),dict):raise ValueError('Ogiltigt söksvar')
        return [{'url':item['url'],'title':str(item.get('title',''))[:250]} for item in data.get('web',{}).get('results',[])[:8]
                if isinstance(item,dict) and isinstance(item.get('url'),str)]
    except (urllib.error.URLError,ValueError,TypeError,KeyError) as error:
        # Never include the API request headers, response body or token in logs/UI.
        raise ValueError('Webbsökningen kunde inte genomföras. Kontrollera söktjänstens anslutning.') from None


def research(company,website='',api_key='',fetch=None,search=None):
    fetch=fetch or outreach.fetch_public
    search=search or brave_search
    company,host=identity(company,website)
    found=[]; visited=set();notes=[];failures=0
    sources=[]
    deadline=time.monotonic()+55
    pending=[website] if website else []
    while pending and len(visited)<4 and time.monotonic()<deadline:
        raw=pending.pop(0)
        try:
            url=outreach.public_url(raw)
            if url in visited or urllib.parse.urlsplit(url).hostname.removeprefix('www.')!=host:continue
            visited.add(url)
            result=fetch(url,timeout=min(5,max(1,deadline-time.monotonic())))
            if 'redirect' in result:
                pending.insert(0,result['redirect']);continue
            contacts,links=extract_contacts(result['html'],url,company,host)
            found+=contacts;sources.append(url)
            for href in links:
                if re.search(r'kontakt|contact|team|inköp|inkop|procurement|about|om-oss',href,re.I):pending.append(urllib.parse.urljoin(url,href))
        except Exception:
            failures+=1
            if raw==website:
                pending.extend(urllib.parse.urljoin(website,path) for path in ('/kontakt','/contact'))
    external_state='not_configured'
    if api_key or search is not brave_search:
        try:
            results=search(company,website,api_key)
            external_state='done'
            for item in results[:8]:
                if time.monotonic()>=deadline:break
                raw=item.get('url','')
                redirects=0
                while redirects<3:
                    try:
                        url=outreach.public_url(raw)
                        if url in visited:break
                        visited.add(url)
                        result=fetch(url,timeout=min(5,max(1,deadline-time.monotonic())))
                        if 'redirect' in result:
                            raw=result['redirect'];redirects+=1;continue
                        external=urllib.parse.urlsplit(url).hostname.removeprefix('www.')!=host
                        contacts,_=extract_contacts(result['html'],url,company,host,external=external)
                        found+=contacts;sources.append(url);break
                    except Exception:
                        failures+=1;break
        except ValueError:
            external_state='failed'
            notes.append('Webbsökningen misslyckades. Kontrollera söktjänstens anslutning.')
    else:
        notes.append('Extern webbsökning är inte ansluten. Företagets webbplats söks igenom när en adress finns.')
    merged={}
    for c in found:
        key=c['email'].casefold() if c['email'] else c['name'].casefold()+'|'+c['role'].casefold()
        old=merged.get(key)
        if old:
            evidence=old.setdefault('sources',[old['source']])
            if c['source'] not in evidence:evidence.append(c['source'])
            if c['name'] and not old['name']:old['name']=c['name']
            if c['role'] and not old['role']:old['role']=c['role']
            old['priority']=old['priority'] or c['priority']
            if c['context'] and c['context'] not in old['context']:old['context']=(old['context']+' · '+c['context'])[:700]
        else:
            c['sources']=[c['source']];merged[key]=c
    contacts=sorted(merged.values(),key=lambda c:(not c['priority'],not bool(c['email']),c['name'] or c['email']))[:30]
    notes.insert(0,f'{len(contacts)} kontaktförslag hittades på {len(sources)} lästa sidor.' if contacts else f'Inga kontaktförslag hittades på {len(sources)} lästa sidor. Du kan lägga till egna kontakter.')
    if failures:notes.append(f'{failures} sidor kunde inte läsas.')
    if any(not c['email'] for c in contacts):notes.append('Vissa personer saknar offentlig e-postadress. Ingen adress har gissats.')
    return {'contacts':contacts,'lookup_note':' '.join(notes),'external_state':external_state,'sources':sources,'failures':failures}
