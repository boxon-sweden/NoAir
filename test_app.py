from __future__ import annotations
import io
from datetime import datetime,timedelta,timezone
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app import create_app, config_from_env, database, PH, purge, MAX_BODY

PASSWORD='test-only-noair-password-2026'
HASH=PH.hash(PASSWORD)

@pytest.fixture
def config(tmp_path):
    c=config_from_env()
    c.update(secret='test-secret-'*5,admin_username='admin',admin_password_hash=HASH,data_dir=str(tmp_path),mode='development',public_origin='http://testserver',submissions_enabled=True)
    return c

@pytest.fixture
def client(config):
    with TestClient(create_app(config)) as cli:
        yield cli

def csrf(client):return client.get('/api/session').json()['csrf']
def image(exif=False):
    buffer=io.BytesIO(); im=Image.new('RGB',(80,60),'white')
    if exif:
        tags=Image.Exif();tags[315]='SHOULD NOT BE RETAINED';tags[270]='private metadata';im.save(buffer,'JPEG',exif=tags)
    else:im.save(buffer,'PNG')
    return buffer.getvalue()
def data(**overrides):
    base={'company':'Testbutik','website':'butik.example','issues':'air','category':'Elektronik','comment':'Test comment','privacy_confirmed':'true','contact_permission':'false','email':'','company_fax':''}
    base.update(overrides);return base

def submit(client, fields=None, raw=None):
    token=csrf(client)
    return client.post('/api/reports',data=fields or data(),files=[('photos',('photo.png',raw if raw is not None else image(),'image/png'))],headers={'X-CSRF-Token':token})

def login(client):
    token=csrf(client)
    response=client.post('/api/login',json={'username':'admin','password':PASSWORD},headers={'X-CSRF-Token':token})
    assert response.status_code==200,response.text
    return response.json()['csrf']

def test_home_and_security_headers(client):
    r=client.get('/');assert r.status_code==200;assert 'noair' in r.text
    assert "script-src 'self'" in r.headers['content-security-policy']
    assert r.headers['x-content-type-options']=='nosniff'

def test_health(client):assert client.get('/healthz').json()=={'status':'ok'}

def test_private_reports_and_images(client):
    assert client.get('/api/admin/reports').status_code==401
    assert client.get('/api/admin/reports/NA-123').status_code==401
    assert client.get('/api/admin/images/'+'a'*32+'.jpg').status_code==401
    assert client.get('/api/reports').status_code==405

def test_csrf_required(client):
    csrf(client)
    r=client.post('/api/reports',data=data(),files={'photos':('a.png',image(),'image/png')})
    assert r.status_code==403

def test_origin_required_to_match(client):
    token=csrf(client)
    r=client.post('/api/reports',data=data(),files={'photos':('a.png',image(),'image/png')},headers={'X-CSRF-Token':token,'Origin':'https://evil.example'})
    assert r.status_code==403

def test_submission_and_admin_read(client):
    r=submit(client);assert r.status_code==201,r.text;receipt=r.json();assert receipt['id'].startswith('NA-');assert len(receipt['deletion_token'])>=32
    login(client);listed=client.get('/api/admin/reports').json()['reports'];assert len(listed)==1
    assert 'email' not in listed[0] and 'comment' not in listed[0]
    detail=client.get('/api/admin/reports/'+receipt['id']).json();assert detail['comment']=='Test comment';assert len(detail['images'])==1
    assert client.get(detail['images'][0]).status_code==200

@pytest.mark.parametrize('overrides',[{'company':''},{'privacy_confirmed':'false'},{'issues':'invalid'},{'category':'invalid'},{'company_fax':'bot'},{'comment':'x'*1501}])
def test_validation(client,overrides):assert submit(client,data(**overrides)).status_code==400

def test_missing_image(client):
    r=client.post('/api/reports',data=data(),headers={'X-CSRF-Token':csrf(client)})
    assert r.status_code==400

def test_more_than_three_images(client):
    files=[('photos',(str(i)+'.png',image(),'image/png')) for i in range(4)]
    r=client.post('/api/reports',data=data(),files=files,headers={'X-CSRF-Token':csrf(client)})
    assert r.status_code==400

def test_fake_image(client):assert submit(client,raw=b'<script>alert(1)</script>').status_code==400

def test_metadata_removed(client):
    r=submit(client,raw=image(exif=True));assert r.status_code==201
    login(client);src=client.get('/api/admin/reports/'+r.json()['id']).json()['images'][0]
    uploaded=client.get(src);parsed=Image.open(io.BytesIO(uploaded.content));assert parsed.format=='JPEG';assert not parsed.getexif();assert b'SHOULD NOT' not in uploaded.content

@pytest.mark.parametrize('overrides',[{'email':'person@example.com'},{'email':'invalid','contact_permission':'true'},{'contact_permission':'true'}])
def test_email_permission(client,overrides):assert submit(client,data(**overrides)).status_code==400

def test_optional_email(client):
    r=submit(client,data(email='person@example.com',contact_permission='true'));assert r.status_code==201
    login(client);detail=client.get('/api/admin/reports/'+r.json()['id']).json();assert detail['contact_permission'] is True;assert detail['contact_permission_at']

@pytest.mark.parametrize('website',['javascript:alert(1)','ftp://bad.example','https://user:password@bad.example','http://bad.example:8080'])
def test_invalid_website(client,website):assert submit(client,data(website=website)).status_code==400

def test_review_guard(client):
    report=submit(client).json()['id'];token=login(client)
    body={'status':'contacted','notes':'','review_checked':False}
    assert client.patch('/api/admin/reports/'+report,json=body,headers={'X-CSRF-Token':token}).status_code==400
    body['review_checked']=True
    assert client.patch('/api/admin/reports/'+report,json=body,headers={'X-CSRF-Token':token}).status_code==200
    assert client.get('/api/admin/reports/'+report).json()['status']=='contacted'

def test_csv_formula_and_no_contact_data(client):
    assert submit(client,data(company='=1+1',comment='secret-private-comment',email='private@example.com',contact_permission='true')).status_code==201
    login(client);r=client.get('/api/admin/export');assert r.status_code==200
    assert "'=1+1" in r.text;assert 'private@example.com' not in r.text;assert 'secret-private-comment' not in r.text

def test_public_delete_and_private_disk(client,config):
    receipt=submit(client).json();token=csrf(client)
    assert client.post('/api/reports/delete',json={'id':receipt['id'],'token':'wrong'},headers={'X-CSRF-Token':token}).status_code==400
    response=client.post('/api/reports/delete',json={'id':receipt['id'],'token':receipt['deletion_token']},headers={'X-CSRF-Token':token})
    assert response.status_code==200
    from pathlib import Path
    assert not list((Path(config['data_dir'])/'images').glob('*.jpg'))
    login(client);assert client.get('/api/admin/reports').json()['reports']==[]

def test_admin_delete_requires_csrf(client):
    report=submit(client).json()['id'];token=login(client)
    assert client.delete('/api/admin/reports/'+report).status_code==403
    assert client.delete('/api/admin/reports/'+report,headers={'X-CSRF-Token':token}).status_code==200

def test_logout_revokes_session(client):
    token=login(client);old_cookie=client.cookies.get('noair_session')
    assert client.post('/api/logout',json={},headers={'X-CSRF-Token':token}).status_code==200
    client.cookies.clear();client.cookies.set('noair_session',old_cookie)
    assert client.get('/api/admin/reports').status_code==401

def test_login_limit(client):
    token=csrf(client)
    for _ in range(8):
        assert client.post('/api/login',json={'username':'admin','password':'wrong'},headers={'X-CSRF-Token':token}).status_code==401
    assert client.post('/api/login',json={'username':'admin','password':'wrong'},headers={'X-CSRF-Token':token}).status_code==429

def test_body_limit(client):
    r=client.post('/api/reports',content=b'x',headers={'Content-Length':str(MAX_BODY+1)})
    assert r.status_code==413

def test_retention(client,config):
    report=submit(client).json()['id'];login(client)
    old=(datetime.now(timezone.utc)-timedelta(days=181)).isoformat()
    with database(config) as db:db.execute('UPDATE reports SET created_at=? WHERE id=?',(old,report))
    assert client.get('/api/admin/reports/'+report).status_code==404
    assert purge(config)==1
    assert client.get('/api/admin/reports').json()['reports']==[]

def test_production_privacy_guard(config):
    config.update(mode='production',public_origin='https://noair.se',submissions_enabled=True,privacy_ready=False)
    with pytest.raises(RuntimeError,match='privacy'):create_app(config)

def test_collection_can_be_disabled(config):
    config['submissions_enabled']=False
    with TestClient(create_app(config)) as client:assert submit(client).status_code==503

def test_production_cookie_and_host(config):
    config.update(mode='production',public_origin='https://noair.se',submissions_enabled=False)
    with TestClient(create_app(config),base_url='https://noair.se') as client:
        r=client.get('/api/session');assert r.status_code==200
        assert 'Secure' in r.headers['set-cookie'] and 'HttpOnly' in r.headers['set-cookie']
        assert 'max-age=31536000' in r.headers['strict-transport-security']
        assert client.get('/',headers={'Host':'evil.example'}).status_code==400

def test_path_traversal_not_exposed(client):
    assert client.get('/static/%2e%2e/data/noair.sqlite3').status_code==404
    assert client.get('/data/noair.sqlite3').status_code==404
