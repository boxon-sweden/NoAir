"""End-to-end admin queue checks using synthetic data; never sends real emails."""
from pathlib import Path
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from argon2 import PasswordHasher
from PIL import Image
from outreach import draft_for
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent
checks=[]

def check(label,condition=True):
    assert condition,label
    checks.append(label)


def review(page,report_id):
    page.locator(f'[data-report-id="{report_id}"]').click()
    page.locator('#detail-status').select_option('reviewed')
    page.locator('#review-checked').check()
    page.locator('#save-report').click()
    expect(page.locator('#show-outreach')).to_be_enabled()
    page.locator('#edit-outreach').click()
    expect(page.locator('#outreach-dialog')).to_be_visible()


def fill_ready(page, demo):
    if demo:
        page.locator('#lookup-outreach-contacts').click()
        page.get_by_role('button',name='Använd kontakt',exact=True).click()
        expect(page.locator('#outreach-email')).to_have_value('inkop@exempelbutik.example')
        check('Demo lookup shows a clearly fictitious contact without network calls')
    else:
        page.locator('#outreach-email').fill('inkop@butik.example')
        page.locator('#outreach-source').fill('https://butik.example/kontakt')
    page.locator('#outreach-name').fill('Fiktiv inköpskontakt')
    page.locator('#outreach-role').fill('Emballageinköp')
    page.locator('#outreach-body').fill('Hej!\n\nFiktiv och granskad dialog om en bättre anpassad förpackning.\n\nBoxon')
    page.locator('#outreach-contact-checked').check()
    page.locator('#outreach-content-checked').check()
    page.locator('#ready-outreach').click()
    expect(page.locator('#outreach-dialog')).not_to_be_visible()

with tempfile.TemporaryDirectory(prefix='noair-outreach-qa-') as tmp_name:
    tmp=Path(tmp_name)
    password=secrets.token_urlsafe(24)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=os.environ.copy()
    env.update(APP_ENV='development',SECRET_KEY=secrets.token_urlsafe(48),ADMIN_PASSWORD_HASH=PasswordHasher().hash(password),ADMIN_USERNAME='admin',DATA_DIR=str(tmp/'data'),SUBMISSIONS_ENABLED='1',CONTACT_LOOKUP_ENABLED='0',OUTREACH_MAIL_ENABLED='0',PUBLIC_ORIGIN=f'http://127.0.0.1:{port}')
    server=subprocess.Popen([sys.executable,'-m','uvicorn','asgi:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz',timeout=1);break
            except Exception:time.sleep(.1)
        else:raise AssertionError('Local test server failed to start')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            page=context.new_page();errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append(r.url))
            page.set_content((ROOT/'noair-forhandsvisning.html').read_text())
            pitch_cases=[
                {'company':'Testbutik','category':'Elektronik','issues':['air','oversized'],'comment':'Jag beställde hörlurar och lådan var för stor.'},
                {'company':'Butik & Co','category':'Hem & inredning','issues':['protection','air'],'comment':'Det var inte hörlurar. Jag fick en laddare.'},
                {'company':'Exempel','category':'Kläder & skor','issues':['filler'],'comment':'Köpte skor. Frågor: privat@example.invalid.'},
                {'company':'Annat','category':'','issues':['other'],'comment':'Ingen produkt angiven.'},
            ]
            for report in pitch_cases:
                actual=page.evaluate('(r)=>window.noairSalesDrafts(r)',report)
                assert actual==[draft_for(report,i) for i in range(3)]
            check('All sales pitch variants match between demo and backend, with report-specific products')
            page.locator('[data-view="admin"]').click()
            expect(page.locator('.outreach-queue-item')).to_have_count(3)
            check('Every demo report receives an outreach draft')
            page.locator('[data-outreach-edit="DEMO-001"]').click()
            expect(page.locator('#ready-outreach')).to_be_disabled()
            check('Unreviewed report cannot enter the send queue')
            page.locator('#outreach-dialog [data-close]').click()
            review(page,'DEMO-001')
            old=page.locator('#outreach-body').input_value()
            page.locator('#outreach-content-checked').check()
            page.locator('#outreach-variant').select_option('1')
            page.locator('#vary-outreach').click()
            check('Alternative wording is available',page.locator('#outreach-body').input_value()!=old)
            expect(page.locator('#outreach-content-checked')).not_to_be_checked()
            fill_ready(page,True)
            page.locator('[data-outreach-edit="DEMO-001"]').click()
            expect(page.locator('#outreach-name')).to_have_value('Fiktiv inköpskontakt')
            expect(page.locator('#outreach-body')).to_have_value('Hej!\n\nFiktiv och granskad dialog om en bättre anpassad förpackning.\n\nBoxon')
            check('Edited message and contact survive closing and reopening')
            page.locator('#outreach-subject').fill('Fiktivt ämne efter redigering')
            expect(page.locator('#outreach-content-checked')).not_to_be_checked()
            check('Editing content invalidates its review checkbox')
            page.locator('#save-outreach-draft').click()
            expect(page.locator('[data-outreach-send="DEMO-001"]')).to_have_count(0)
            check('Saving edits as draft removes it from the ready queue')
            page.locator('[data-outreach-edit="DEMO-001"]').click()
            page.locator('#outreach-content-checked').check()
            page.locator('#ready-outreach').click()
            page.locator('[data-outreach-send="DEMO-001"]').click()
            page.locator('#outreach-filter').select_option('sent')
            expect(page.locator('.outreach-state')).to_have_text('Simulerat utskick')
            check('A ready message sends in one click as a clearly labeled simulation')
            check('Demo performs no HTTP requests',not any(u.startswith(('http://','https://')) for u in requests))
            page.locator('#outreach-filter').select_option('all')
            for width in [320,390,820,1440]:
                page.set_viewport_size({'width':width,'height':900})
                check(f'Queue fits {width}px',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                page.locator('[data-outreach-edit="DEMO-002"]').click()
                check(f'Editor fits {width}px',page.locator('#outreach-dialog').evaluate('(d)=>d.scrollWidth<=d.clientWidth'))
                page.locator('#outreach-dialog [data-close]').click()
            live=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            live.on('pageerror',lambda e:errors.append(str(e)))
            live.goto(f'http://127.0.0.1:{port}/')
            sample=tmp/'synthetic.png';Image.new('RGB',(100,80),'white').save(sample)
            live.locator('#photos').set_input_files(str(sample))
            live.locator('#company').fill('Fiktiv kötestbutik')
            live.locator('#website').fill('butik.example')
            live.locator('label').filter(has=live.locator('input[value="air"]')).click()
            live.locator('#privacy-confirmed').check()
            live.locator('#submit-report').click()
            expect(live.locator('#report-success')).to_be_visible()
            report_id=live.locator('#receipt-id').inner_text()
            live.goto(f'http://127.0.0.1:{port}/admin')
            live.locator('#username').fill('admin');live.locator('#password').fill(password);live.locator('#login-form button').click()
            expect(live.locator('.outreach-queue-item')).to_have_count(1)
            check('Real backend creates a persistent draft on submission')
            review(live,report_id)
            fill_ready(live,False)
            expect(live.locator(f'[data-outreach-send="{report_id}"]')).to_be_disabled()
            check('Live email stays blocked until eMarketeer is connected')
            live.reload()
            expect(live.locator('.outreach-state')).to_have_text('Klar för utskick')
            live.locator(f'[data-outreach-edit="{report_id}"]').click()
            expect(live.locator('#outreach-email')).to_have_value('inkop@butik.example')
            expect(live.locator('#outreach-role')).to_have_value('Emballageinköp')
            check('Queue and edited contact persist across backend page reload')
            check('Both demo and backend have no JavaScript errors',not errors)
            browser.close()
    finally:
        server.terminate();server.wait(timeout=10)
print(f'{len(checks)} outreach browser checks passed (offline demo + real backend). No real email sent.')
for label in checks:print('  '+label)
