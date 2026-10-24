"""Noair v2 browser regression tests (offline demo and local server).
Run: python test_browser.py. Requires Chromium and the dev requirements.
Only synthetic images and fictitious companies are used.
"""
from pathlib import Path
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from argon2 import PasswordHasher

ROOT=Path(__file__).resolve().parent
PASSWORD='qa-only-noair-password-2026'
checks=[]

def check(name,condition):
    assert condition,name
    checks.append(name)

def image_upload(page,image_file):
    page.locator('#photos').set_input_files(str(image_file))
    expect(page.locator('.photo-preview')).to_have_count(1)

def choose_issue(page,value):
    page.locator('.issue-chips label').filter(has=page.locator('input[value="'+value+'"]')).click()

def valid_fields(page,company='Testbutik Browser'):
    page.locator('#company').fill(company)
    page.locator('#website').fill('testbutik.example')
    choose_issue(page,'air')
    choose_issue(page,'oversized')
    page.locator('#comment').fill('Testdata: en liten produkt i en stor kartong.')
    page.locator('#category').select_option(label='Elektronik')
    page.locator('#privacy-confirmed').check()

def submit(page):
    page.locator('#submit-report').click()
    expect(page.locator('#report-success')).to_be_visible()
    check('Receipt is shown after successful submission',bool(page.locator('#receipt-id').inner_text()))

def save_receipt(page,tmp):
    with page.expect_download() as d:
        page.locator('#save-receipt').click()
    path=tmp/d.value.suggested_filename;d.value.save_as(path)
    content=path.read_text()
    reference=next(l.split(': ',1)[1] for l in content.splitlines() if l.startswith('Rapport: '))
    token=next(l.split(': ',1)[1] for l in content.splitlines() if l.startswith('Privat raderingskod: '))
    check('Downloaded receipt contains reference and deletion code',bool(reference and token))
    return reference,token

def review_report(page):
    page.locator('[data-report-id]').first.click()
    expect(page.locator('#detail-dialog')).to_be_visible()
    check('Contact draft is blocked before manual review',page.locator('#show-outreach').is_disabled())
    page.locator('#detail-status').select_option('reviewed')
    page.locator('#save-report').click()
    expect(page.locator('#detail-error')).not_to_be_empty()
    check('Changing to reviewed without review confirmation is blocked',bool(page.locator('#detail-error').inner_text()))
    page.locator('#review-checked').check()
    page.locator('#detail-notes').fill('Testanteckning, inte en verklig kundkontakt.')
    page.locator('#save-report').click()
    expect(page.locator('#show-outreach')).to_be_enabled()
    page.locator('#show-outreach').click()
    expect(page.locator('#outreach-panel')).to_be_visible()
    check('Reviewed report enables contact draft without sending',bool(page.locator('#outreach-text').inner_text()))
    page.locator('#detail-dialog [data-close]').click()

with tempfile.TemporaryDirectory(prefix='noair-v2-qa-') as tmp_string:
    tmp=Path(tmp_string)
    sample=tmp/'test-photo.png';Image.new('RGB',(640,480),(220,225,210)).save(sample)
    bad=tmp/'not-an-image.txt';bad.write_text('test')
    large=tmp/'too-large.png';large.write_bytes(b'\0'*(8*1024*1024+1))
    with sync_playwright() as p:
        browser_path = os.getenv('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('chromium-browser')
        browser_options = {'executable_path': browser_path} if browser_path else {}
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'],**browser_options)
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True,reduced_motion='reduce')
        page=context.new_page();errors=[];requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url))
        page.set_content((ROOT/'noair-forhandsvisning.html').read_text(encoding='utf-8'))
        expect(page.locator('#preview-bar')).to_be_visible()
        check('All original questions are shown in the inline card',all(page.locator(s).is_visible() for s in ['#company','#website','.issue-field','#comment','#category','#email','#privacy-confirmed','#contact-permission']))
        check('Desktop has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.locator('.na-hero [data-open-report]').click()
        check('Hero button scrolls to inline form rather than opening a modal',page.locator('#report-dialog').evaluate('(e)=>e.tagName==="DIV"&&e.getBoundingClientRect().top>=0&&e.getBoundingClientRect().top<100'))
        page.locator('#submit-report').click();expect(page.locator('#upload-zone')).to_have_attribute('aria-invalid','true')
        check('At least one photo remains mandatory',bool(page.locator('#report-error').inner_text()))
        page.locator('#photos').set_input_files(str(bad));expect(page.locator('#photo-error')).not_to_be_empty()
        check('Unsupported file type is rejected',page.locator('.photo-preview').count()==0)
        page.locator('#photos').set_input_files(str(large));expect(page.locator('#photo-error')).to_contain_text('8 MB')
        check('Original 8 MB per-photo limit remains enforced',page.locator('.photo-preview').count()==0)
        image_upload(page,sample)
        page.locator('#photos').set_input_files([str(sample)]*3)
        expect(page.locator('.photo-preview')).to_have_count(3)
        expect(page.locator('#photo-error')).not_to_be_empty()
        check('Original three-photo limit remains enforced',page.locator('.photo-preview').count()==3)
        page.locator('.photo-preview button').last.click();page.locator('.photo-preview button').last.click()
        check('Selected images can be removed',page.locator('.photo-preview').count()==1)
        page.locator('#submit-report').click();expect(page.locator('#company')).to_have_attribute('aria-invalid','true')
        check('Company remains mandatory',bool(page.locator('#report-error').inner_text()))
        page.locator('#company').fill('Testbutik Browser')
        page.locator('#website').fill('not-a-website')
        page.locator('#submit-report').click();expect(page.locator('#website')).to_have_attribute('aria-invalid','true')
        check('Invalid website shows an inline error',True)
        page.locator('#website').fill('testbutik.example')
        page.locator('#submit-report').click();expect(page.locator('.issue-field')).to_have_attribute('aria-invalid','true')
        check('At least one issue remains mandatory',True)
        choose_issue(page,'air');choose_issue(page,'oversized')
        check('Multiple issue choices remain possible',page.locator('input[name="issues"]:checked').count()==2)
        page.locator('#comment').fill('Testdata: en liten produkt i en stor kartong.')
        page.locator('#category').select_option(label='Elektronik')
        page.locator('#submit-report').click();expect(page.locator('#privacy-confirmed')).to_have_attribute('aria-invalid','true')
        check('Privacy confirmation remains mandatory',True)
        page.locator('#privacy-confirmed').check()
        page.locator('#email').fill('noair-test@example.invalid')
        page.locator('#submit-report').click();expect(page.locator('#contact-permission')).to_have_attribute('aria-invalid','true')
        check('Email use still requires separate contact permission',True)
        page.locator('#email').fill('invalid')
        page.locator('#submit-report').click();expect(page.locator('#email')).to_have_attribute('aria-invalid','true')
        check('Invalid email cannot be submitted',True)
        page.locator('#email').fill('')
        submit(page)
        reference,token=save_receipt(page,tmp)
        page.locator('[data-view="admin"]').click();expect(page.locator('#stat-total')).to_have_text('4')
        check('Demo submission appears alongside three labelled fictitious examples',page.locator('#admin-demo-note').is_visible())
        page.locator('#report-search').fill('Testbutik Browser')
        expect(page.locator('[data-report-id]')).to_have_count(1)
        check('Admin search finds the new report',True)
        review_report(page)
        with page.expect_download() as d:page.locator('#export-csv').click()
        csv=tmp/d.value.suggested_filename;d.value.save_as(csv)
        check('CSV overview excludes comments and consumer contact data','Testdata:' not in csv.read_text() and 'noair-test@' not in csv.read_text())
        page.locator('[data-view="public"]').click()
        page.locator('.na-footer [data-privacy]').click();expect(page.locator('#privacy-dialog')).to_be_visible()
        check('Privacy information is still available',bool(page.locator('#privacy-content').inner_text()))
        page.locator('#privacy-dialog [data-close]').click()
        page.locator('.na-footer [data-deletion]').click()
        page.locator('#delete-reference').fill(reference);page.locator('#delete-token').fill(token)
        page.locator('#delete-form button').click();expect(page.locator('#delete-success')).to_be_visible()
        check('Receipt-based deletion still works',True)
        page.locator('#delete-dialog [data-close]').click()
        page.locator('[data-view="admin"]').click();expect(page.locator('#stat-total')).to_have_text('3')
        check('Deleted report is removed from demo dashboard',True)
        page.locator('[data-view="public"]').click()
        page.locator('#new-report').click()
        expect(page.locator('#report-form')).to_be_visible()
        check('New report resets the inline form',page.locator('#company').input_value()=='' and page.locator('.photo-preview').count()==0)
        for width in [320,375,390,768,820,1024,1920]:
            page.set_viewport_size({'width':width,'height':900})
            check(f'No horizontal overflow at {width}px',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            check(f'Form card fits viewport at {width}px',page.locator('.na-report-card').bounding_box()['width']<=width)
        page.set_viewport_size({'width':390,'height':844})
        image_upload(page,sample);valid_fields(page,'Mobiltestbutik');submit(page)
        check('Complete mobile submission works with original questions',page.locator('#report-success').is_visible())
        check('Offline demo makes no HTTP requests',not any(u.startswith(('http://','https://')) for u in requests))
        check('Offline demo has no JavaScript runtime errors',not errors)
        context.close()
        live_tested=os.getenv('NOAIR_OFFLINE_QA')!='1'
        if live_tested:
            env=os.environ.copy();env.update(APP_ENV='development',SECRET_KEY='qa-only-secret-'*5,ADMIN_PASSWORD_HASH=PasswordHasher().hash(PASSWORD),ADMIN_USERNAME='admin',DATA_DIR=str(tmp/'data'),SUBMISSIONS_ENABLED='1',PUBLIC_ORIGIN='http://127.0.0.1:8877')
            process=subprocess.Popen([sys.executable,'-m','uvicorn','asgi:app','--host','127.0.0.1','--port','8877','--no-access-log'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                for _ in range(80):
                    try:urllib.request.urlopen('http://127.0.0.1:8877/healthz',timeout=1);break
                    except Exception:time.sleep(.15)
                else:raise RuntimeError('QA server failed to start: '+process.stderr.read().decode())
                ctx=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce',accept_downloads=True)
                live=ctx.new_page();live_errors=[];live.on('pageerror',lambda e:live_errors.append(str(e)))
                live.goto('http://127.0.0.1:8877/');expect(live.locator('#local-banner')).to_be_visible()
                expect(live.locator('.na-hero-art img')).to_be_visible()
                check('Server serves new artwork',live.locator('.na-hero-art img').evaluate('(e)=>e.complete&&e.naturalWidth>0'))
                check('Server serves new design stylesheet',live.locator('.na-form-section').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(32, 62, 45)')
                image_upload(live,sample);valid_fields(live,'Backend Testbutik');submit(live)
                reference,token=save_receipt(live,tmp)
                live.goto('http://127.0.0.1:8877/admin')
                live.locator('#username').fill('admin');live.locator('#password').fill(PASSWORD);live.locator('#login-form button').click()
                expect(live.locator('#dashboard')).to_be_visible();expect(live.locator('#stat-total')).to_have_text('1')
                check('Real database submission reaches authenticated admin view',True)
                live.locator('[data-report-id]').first.click()
                expect(live.locator('.detail-photos img')).to_be_visible()
                check('Stored image can be loaded by authenticated admin',live.locator('.detail-photos img').evaluate('(e)=>e.complete&&e.naturalWidth>0'))
                live.locator('#detail-dialog [data-close]').click()
                review_report(live)
                live.locator('#logout').click();expect(live.locator('#login-panel')).to_be_visible()
                check('Admin logout still works',True)
                live.goto('http://127.0.0.1:8877/')
                live.locator('.na-footer [data-deletion]').click()
                live.locator('#delete-reference').fill(reference);live.locator('#delete-token').fill(token)
                live.locator('#delete-form button').click();expect(live.locator('#delete-success')).to_be_visible()
                check('Real backend receipt-based deletion still works',True)
                check('Server-rendered app has no JavaScript runtime errors',not live_errors)
                ctx.close()
            finally:
                process.terminate();process.wait(timeout=10)
        browser.close()

result={'version':2,'passed':len(checks),'live_browser_backend_tested':live_tested,'engine':'Chromium','checks':checks}
(ROOT/'testresultat-webblasare-v2.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
