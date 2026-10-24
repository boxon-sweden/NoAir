"""Public contact research fixtures: website first, scoped external evidence."""
import json
import urllib.error

import contact_research as research


def test_website_then_cases_and_news_with_real_source_evidence():
    pages={
        'https://butik.example/':'<a href="/kontakt">Kontakt</a><p>info@butik.example</p>',
        'https://butik.example/kontakt':'<div><h3>Anna Andersson</h3><p>Inköpschef</p><a href="mailto:anna@butik.example">Mejla Anna</a></div>',
        'https://leverantor.example/kundcase':'<article>Butik AB: Erik Eriksson, logistikchef, erik@butik.example.</article><footer><p>Press: press@leverantor.example</p></footer>',
        'https://nyheter.example/artikel':'<article>Butik AB har utvecklat sin förpackning. Kim Karlsson, förpackningsansvarig på Butik AB, berättar om projektet.</article><footer>redaktion@nyheter.example</footer>',
    }
    calls=[]
    def fetch(url,timeout=5):calls.append(url);return {'html':pages[url]}
    def search(company,website,key):
        assert company=='Butik AB' and website=='https://butik.example/' and key=='test-key'
        assert calls==list(pages)[:2]
        return [{'url':url} for url in list(pages)[2:]]
    result=research.research('Butik AB','https://butik.example/',api_key='test-key',fetch=fetch,search=search)
    assert result['external_state']=='done' and calls==list(pages)
    emails={c['email'] for c in result['contacts']}
    assert 'anna@butik.example' in emails and 'erik@butik.example' in emails
    assert 'press@leverantor.example' not in emails and 'redaktion@nyheter.example' not in emails
    anna=next(c for c in result['contacts'] if c['email']=='anna@butik.example')
    assert anna['name']=='Anna Andersson' and anna['role']=='Inköpschef'
    kim=next(c for c in result['contacts'] if c['name']=='Kim Karlsson')
    assert kim['email']=='' and kim['origin']=='external'


def test_structured_public_person_and_company_scope():
    graph={'@graph':[{'@type':'Person','name':'Anna Andersson','jobTitle':'Inköpschef','worksFor':{'name':'Butik AB'},'email':'anna@butik.example'},
                     {'@type':'Person','name':'Erik Eriksson','jobTitle':'Inköpschef','worksFor':{'name':'Annan AB'},'email':'erik@annan.example'}]}
    html='<script type="application/ld+json">'+json.dumps(graph)+'</script>'
    contacts,_=research.extract_contacts(html,'https://nyheter.example/','Butik AB','butik.example',external=True)
    assert len(contacts)==1 and contacts[0]['name']=='Anna Andersson'


def test_missing_search_connection_is_explicit_not_fake_results():
    result=research.research('Butik AB','https://butik.example/',fetch=lambda url,timeout=5:{'html':'<p>Inga kontakter publicerade.</p>'})
    assert result['contacts']==[] and result['external_state']=='not_configured'
    assert 'inte ansluten' in result['lookup_note']


def test_search_without_website_and_unrelated_external_contacts_rejected():
    result=research.research('Butik AB','',search=lambda *args:[{'url':'https://nyheter.example/'}],fetch=lambda url,timeout=5:{'html':'<p>En annan firma. Inköpschef Anna Andersson, anna@annan.example.</p>'})
    assert result['contacts']==[]


def test_api_failure_still_preserves_website_contacts():
    def broken(*args):raise ValueError('No API access')
    result=research.research('Butik AB','https://butik.example/',fetch=lambda url,timeout=5:{'html':'<p>Inköp: inkop@butik.example</p>'},search=broken)
    assert result['contacts'][0]['email']=='inkop@butik.example'
    assert result['external_state']=='failed' and 'misslyckades' in result['lookup_note']


def test_redirects_are_validated_and_read_failures_are_visible():
    calls=[]
    def fetch(url,timeout=5):calls.append(url);return {'redirect':'http://127.0.0.1/private'}
    result=research.research('Butik AB','https://butik.example/',fetch=fetch)
    assert calls==['https://butik.example/'] and result['contacts']==[] and result['failures']==1


def test_brave_request_uses_fixed_https_endpoint_and_only_company_query(monkeypatch):
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return json.dumps({'web':{'results':[{'url':'https://nyheter.example/case','title':'Case'}]}}).encode()
    def request(req,timeout):
        assert req.full_url.startswith('https://api.search.brave.com/res/v1/web/search?')
        assert req.get_header('X-subscription-token')=='synthetic-key'
        assert req.get_header('Authorization') is None
        assert 'kundkommentar' not in req.full_url
        return Response()
    class Opener:
        def open(self,req,timeout):return request(req,timeout)
    monkeypatch.setattr(research.urllib.request,'build_opener',lambda *args:Opener())
    assert research.brave_search('Butik AB','https://butik.example','synthetic-key')[0]['url']=='https://nyheter.example/case'


def test_external_footer_cannot_become_target_contact_via_shared_page_wrapper():
    html='<div><article>Butik AB: Anna Andersson, inköpschef, berättar om emballage.</article><footer><p>Press: press@konkurrent.example</p></footer></div>'
    contacts,_=research.extract_contacts(html,'https://konkurrent.example/case','Butik AB','butik.example',external=True)
    assert not any(c['email']=='press@konkurrent.example' for c in contacts)
    assert any(c['name']=='Anna Andersson' and not c['email'] for c in contacts)
