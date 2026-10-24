"""Outreach workflow tests: real DB, auth/CSRF, delivery adapters and bounded lookup."""
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import outreach
from app import create_app, database, init_database, purge
from tests.test_app import config, client, csrf, submit, login, data


def message_path(report_id):
    return f'/api/admin/reports/{report_id}/outreach'


def reviewed(client):
    receipt = submit(client, data(comment='En laddare i en stor låda. Privat: kund@example.invalid')).json()
    report_id = receipt['id']
    token = login(client)
    response = client.patch(f'/api/admin/reports/{report_id}', json={'status':'reviewed','notes':'','review_checked':True}, headers={'X-CSRF-Token':token})
    assert response.status_code == 200
    return report_id, token


def ready(client):
    report_id, token = reviewed(client)
    m = client.get(message_path(report_id)).json()
    m.update(recipient_email='inkop@butik.example',recipient_name='Testkontakt',recipient_role='Inköp',source_url='https://butik.example/kontakt',state='ready',contact_checked=True,content_checked=True)
    response = client.put(message_path(report_id), json=m, headers={'X-CSRF-Token':token})
    assert response.status_code == 200, response.text
    return report_id, token, response.json()


def send(client, report_id, token, version):
    return client.post(message_path(report_id)+'/send',json={'version':version},headers={'X-CSRF-Token':token})


def test_draft_created_automatically_without_private_customer_data(client):
    report_id, token = reviewed(client)
    m = client.get(message_path(report_id)).json()
    assert m['state']=='draft'
    assert 'tomrum' in m['body'] and 'laddare' in m['body'] and '15 minuter' in m['body']
    assert 'kund@example.invalid' not in m['body']
    assert len(m['variants'])==3 and len({v['body'] for v in m['variants']})==3
    queue=client.get('/api/admin/outreach').json()
    assert queue['messages'][0]['report_id']==report_id
    assert queue['mail_configured'] is False


def test_queue_requires_auth_and_csrf(client):
    receipt=submit(client).json(); path=message_path(receipt['id'])
    for url in ['/api/admin/outreach',path]:
        assert client.get(url).status_code==401
    assert client.put(path,json={}).status_code==401
    token=login(client)
    assert client.put(path,json={}).status_code==403
    assert client.post(path+'/send',json={}).status_code==403
    assert client.post(f"/api/admin/reports/{receipt['id']}/contacts",json={}).status_code==403


def test_ready_requires_review_contact_and_content(client):
    report_id=submit(client).json()['id'];token=login(client)
    m=client.get(message_path(report_id)).json()
    m.update(state='ready',recipient_email='inkop@example.org',contact_checked=True,content_checked=True)
    assert client.put(message_path(report_id),json=m,headers={'X-CSRF-Token':token}).status_code==400
    client.patch(f'/api/admin/reports/{report_id}',json={'status':'reviewed','notes':'','review_checked':True},headers={'X-CSRF-Token':token})
    m=client.get(message_path(report_id)).json()
    m.update(state='ready',recipient_email='inkop@example.org',contact_checked=False,content_checked=True)
    assert client.put(message_path(report_id),json=m,headers={'X-CSRF-Token':token}).status_code==400


def test_ready_can_be_sent_without_editing_and_not_twice(client,config):
    deliveries=[]
    config.update(mail_enabled=True,mail_from='sender@boxon.example',delivery_adapter=deliveries.append)
    report_id,token,m=ready(client)
    result=send(client,report_id,token,m['version'])
    assert result.status_code==200 and result.json()['state']=='sent'
    assert len(deliveries)==1
    assert deliveries[0]['to_email']==m['recipient_email'] and deliveries[0]['body']==m['body']
    assert 'images' not in deliveries[0] and 'kund@example.invalid' not in deliveries[0]['body']
    assert send(client,report_id,token,m['version']).status_code==409
    assert len(deliveries)==1
    assert client.get(f'/api/admin/reports/{report_id}').json()['status']=='contacted'


def test_concurrent_send_claim_and_resolution_lock(client,config):
    entered,release=threading.Event(),threading.Event()
    calls=[]
    def adapter(envelope):
        calls.append(envelope);entered.set();assert release.wait(10)
    config.update(mail_enabled=True,mail_from='sender@boxon.example',delivery_adapter=adapter)
    report_id,token,m=ready(client)
    results=[]
    worker=threading.Thread(target=lambda:results.append(send(client,report_id,token,m['version'])))
    worker.start()
    try:
        assert entered.wait(5)
        assert send(client,report_id,token,m['version']).status_code==409
        sending=client.get(message_path(report_id)).json()
        response=client.post(message_path(report_id)+'/resolve',json={'version':sending['version'],'state':'draft','checked_provider_log':True},headers={'X-CSRF-Token':token})
        assert response.status_code==409
    finally:
        release.set();worker.join(10)
    assert results[0].json()['state']=='sent' and len(calls)==1


def test_unconfigured_send_preserves_ready_queue(client):
    report_id,token,m=ready(client)
    assert send(client,report_id,token,m['version']).status_code==503
    assert client.get(message_path(report_id)).json()['state']=='ready'


@pytest.mark.parametrize('error,state', [(outreach.DeliveryRejected('no'),'failed'), (TimeoutError('unknown'),'uncertain'), (outreach.DeliveryUncertain('unknown'),'uncertain')])
def test_delivery_errors_and_unknown_status_never_auto_retry(client,config,error,state):
    calls=[]
    def adapter(envelope):
        calls.append(envelope);raise error
    config.update(mail_enabled=True,mail_from='sender@boxon.example',delivery_adapter=adapter)
    report_id,token,m=ready(client)
    result=send(client,report_id,token,m['version']).json()
    assert result['state']==state
    assert send(client,report_id,token,result['version']).status_code==409
    assert len(calls)==1
    if state=='uncertain':
        response=client.put(message_path(report_id),json={**m,'version':result['version']},headers={'X-CSRF-Token':token})
        assert response.status_code==409
        assert client.post(message_path(report_id)+'/resolve',json={'state':'draft','version':result['version'],'checked_provider_log':False},headers={'X-CSRF-Token':token}).status_code==400
        assert client.post(message_path(report_id)+'/resolve',json={'state':'draft','version':result['version'],'checked_provider_log':True},headers={'X-CSRF-Token':token}).json()['state']=='draft'


def test_editing_and_optimistic_concurrency(client):
    report_id,token,m=ready(client)
    edited={**m,'body':'Eget fullt redigerat meddelande','recipient_email':'ny@butik.example','state':'draft','content_checked':False}
    saved=client.put(message_path(report_id),json=edited,headers={'X-CSRF-Token':token})
    assert saved.json()['body']==edited['body'] and saved.json()['recipient_email']==edited['recipient_email']
    assert client.put(message_path(report_id),json=edited,headers={'X-CSRF-Token':token}).status_code==409
    assert client.get(message_path(report_id)).json()['state']=='draft'


@pytest.mark.parametrize('changes',[{'subject':'Hej\r\nBcc: other@example.org'},{'recipient_email':'not-email'},{'source_url':'javascript:alert(1)'},{'body':'\0'}])
def test_reject_header_injection_and_invalid_fields(client,changes):
    report_id,token,m=ready(client)
    m.update(changes)
    assert client.put(message_path(report_id),json=m,headers={'X-CSRF-Token':token}).status_code==400


def test_report_review_revocation_removes_ready_state(client):
    report_id,token,m=ready(client)
    client.patch(f'/api/admin/reports/{report_id}',json={'status':'new','notes':'','review_checked':False},headers={'X-CSRF-Token':token})
    assert client.get(message_path(report_id)).json()['state']=='draft'


def test_queue_follows_report_deletion_and_retention(client,config):
    report_id,token,m=ready(client)
    client.delete(f'/api/admin/reports/{report_id}',headers={'X-CSRF-Token':token})
    assert client.get('/api/admin/outreach').json()['messages']==[]
    report_id,token,m=ready(client)
    with database(config) as db:
        db.execute('UPDATE reports SET created_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=181)).isoformat(),report_id))
    assert client.get('/api/admin/outreach').json()['messages']==[]
    assert client.get(message_path(report_id)).status_code==404
    purge(config)
    with database(config) as db:
        assert db.execute('SELECT COUNT(*) FROM outreach').fetchone()[0]==0


def test_backfill_is_repeatable_and_preserves_edited_draft(client,config):
    report_id,token,m=ready(client)
    with database(config) as db:
        db.execute('DELETE FROM outreach WHERE report_id=?',(report_id,))
    init_database(config)
    draft=client.get(message_path(report_id)).json()
    assert draft['state']=='draft'
    draft['body']='Eget utkast'
    assert client.put(message_path(report_id),json=draft,headers={'X-CSRF-Token':token}).status_code==200
    init_database(config)
    assert client.get(message_path(report_id)).json()['body']=='Eget utkast'


def test_public_contact_discovery_sources_priority_and_scope():
    pages={
        'https://butik.example/': '<a href="/kontakt">Kontakt</a><a href="https://external.example/team">Extern</a><p>Allmänt: info@butik.example</p>',
        'https://butik.example/kontakt':'<p>Inköp och emballage: inkop@butik.example</p><a href="mailto:inkop@butik.example">Mejla</a>',
    }
    requested=[]
    def fetch(url,timeout=5):requested.append(url);return {'html':pages[url]}
    result=outreach.lookup_contacts('https://butik.example',fetch=fetch)
    assert result['contacts'][0]['email']=='inkop@butik.example'
    assert result['contacts'][0]['priority'] is True
    assert result['contacts'][0]['source']=='https://butik.example/kontakt'
    assert result['contacts'][0]['role']=='' and result['contacts'][0]['name']==''
    assert requested==list(pages)


@pytest.mark.parametrize('address',['127.0.0.1','10.0.0.1','169.254.169.254','::1','fc00::1'])
def test_lookup_rejects_private_dns_targets(monkeypatch,address):
    monkeypatch.setattr(outreach.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',(address,443))])
    with pytest.raises(ValueError,match='publik'):
        outreach.fetch_public('https://internal.example/')


def test_lookup_does_not_follow_redirects_to_other_hosts():
    calls=[]
    def fetch(url,timeout=5):calls.append(url);return {'redirect':'https://127.0.0.1/kontakt'}
    result=outreach.lookup_contacts('https://butik.example/',fetch=fetch)
    assert len(calls)==1 and result['contacts']==[]


def test_auto_lookup_after_submission_and_manual_refresh(client,config,monkeypatch):
    config['contact_lookup_enabled']=True
    calls=[]
    def lookup(website):calls.append(website);return {'contacts':[],'lookup_note':'Ingen publicerad kontakt.'}
    monkeypatch.setattr(outreach,'lookup_contacts',lookup)
    report_id=submit(client).json()['id'];token=login(client)
    m=client.get(message_path(report_id)).json()
    assert m['lookup_state']=='done' and len(calls)==1
    response=client.post(f'/api/admin/reports/{report_id}/contacts',json={},headers={'X-CSRF-Token':token})
    assert response.status_code==200 and len(calls)==2


def test_public_fetch_pins_ip_and_keeps_tls_hostname_verification(monkeypatch):
    from email.message import Message
    events=[]
    class Sock:
        def settimeout(self,timeout):assert timeout>0
        def connect(self,address):events.append(('connect',address))
        def close(self):pass
    class Response:
        status=200
        headers=Message()
        remaining=b'<p>Inkop: inkop@butik.example</p>'
        def getheader(self,name,default=''):return 'text/html' if name=='Content-Type' else default
        def read1(self,n):
            value=self.remaining[:n];self.remaining=self.remaining[n:];return value
    class Connection:
        def __init__(self,host,timeout,context):
            assert host=='butik.example' and context.check_hostname and context.verify_mode==outreach.ssl.CERT_REQUIRED
            self.sock=None
        def request(self,method,path,headers):
            assert method=='GET' and path=='/kontakt'
            assert not any(k.lower() in ('authorization','cookie') for k in headers)
            self.sock=self._create_connection(('butik.example',443))
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(outreach.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])
    monkeypatch.setattr(outreach.socket,'socket',lambda *a,**k:Sock())
    monkeypatch.setattr(outreach.http.client,'HTTPSConnection',Connection)
    result=outreach.fetch_public('https://butik.example/kontakt')
    assert 'inkop@butik.example' in result['html']
    assert events==[('connect',('8.8.8.8',443))]


@pytest.mark.parametrize('variant',range(3))
def test_sales_pitch_uses_customer_product_boxon_solution_and_meeting(variant):
    report={'company':'Hörlurbutiken','issues':['air','oversized'],'category':'Elektronik',
            'comment':'Jag beställde hörlurar men fick en jättestor låda. Mitt namn: Privat Kund, privat@example.invalid, 0701234567.'}
    draft=outreach.draft_for(report,variant)
    body=draft['body']
    assert 'hörlurar' in body and 'Hörlurbutiken' in body
    assert 'en av era kunder' in body and 'tomrum' in body
    assert 'mindre lådformat och en anpassad insats' in body
    assert '15 minuter' in body and 'nästa vecka' in body and 'Boxon' in body
    assert 'Marcus Gustafsson' in body
    assert not any(value in body for value in ['Privat Kund','privat@example.invalid','0701234567','konkurrent'])
    assert 'garanter' not in body.lower()


def test_product_detection_ignores_negated_and_hypothetical_mentions():
    assert outreach.product_from_text('Det var inte hörlurar. Jag fick en laddare.')=='en laddare'
    assert outreach.product_from_text('Lådan skulle kunna rymma skor.')==''
    assert outreach.product_from_text('Kontakt: hörlurar@example.invalid och https://butik.example/skor')==''
    assert outreach.product_from_text('HÖRLURARNA låg i en stor låda.')=='hörlurar'


def test_pitch_proposal_changes_with_protection_and_filler():
    base={'company':'Butik','category':'','comment':'','issues':['protection','air']}
    protected=outreach.draft_for(base)['body']
    assert 'anpassad stötdämpning' in protected
    assert 'mindre lådformat' not in protected
    base['issues']=['filler']
    filler=outreach.draft_for(base)['body']
    assert 'minska behovet av fyllnadsmaterial' in filler
    assert 'hörlurar' not in filler
    base['category']='Elektronik'
    assert 'en leverans av elektronik' in outreach.draft_for(base)['body']
