"""Report-specific drafts, bounded public contact lookup, and explicit email delivery.

No image uploads to third parties. Contact lookup fetches public HTTPS pages only.
The future eMarketeer adapter is opt-in. Delivery uncertainty is never retried.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}")
LABELS = {'air': 'mycket tomrum', 'filler': 'mycket fyllnadsmaterial', 'oversized': 'en stor låda i förhållande till innehållet', 'protection': 'frågor om produktskyddet', 'other': 'förpackningens utformning'}
ROLE = re.compile(r'inköp|emballage|förpackning|packaging|procurement|purchasing|supply chain|logistik', re.I)


def valid_email(value):
    return isinstance(value, str) and len(value) <= 254 and EMAIL.fullmatch(value) is not None


def draft_for(report, variant=0):
    """Use structured observations. Private free text is for internal review only."""
    company = re.sub(r'[\r\n\x00-\x1f]', ' ', report['company']).strip()
    labels = [LABELS[x] for x in report['issues'] if x in LABELS]
    insight = ', '.join(labels) or 'förpackningens utformning'
    openings = [
        f'Via Noair, ett initiativ av Boxon, har vi fått en observation om {insight} i en leverans från {company}.',
        f'Vi på Boxon vill gärna prata med er om förpackningar. En observation via Noair om en leverans från {company} rör {insight}.',
        f'Kan en mer anpassad förpackning vara intressant för {company}? Via Noair har vi fått en observation som rör {insight}.',
    ]
    category = report.get('category', '')
    category_line = f' Rapporten gäller produktkategorin {category}.' if category else ''
    # Do not forward arbitrary customer text. Use only a fixed vocabulary of
    # packaging/product terms, with clear attribution rather than inferred facts.
    comment = report.get('comment', '')
    terms = [term for term in ('laddare', 'skor', 'kläder', 'glas', 'papper', 'plast', 'luft')
             if re.search(r'\b'+term+r'\b', comment, re.I)]
    if terms:
        category_line += ' I beskrivningen nämns ' + ', '.join(terms[:3]) + '.' 
    body = ('Hej!\n\n' + openings[variant % len(openings)] + category_line +
            '\n\nDet är en enskild kundobservation, inte en fullständig bedömning av er förpackningslösning. Vi vill gärna förstå era krav på produktskydd och packning och undersöka om en mer anpassad lösning kan vara relevant.' +
            '\n\nÄr du rätt person att prata med om inköp av emballage, eller kan du hänvisa oss vidare? Har ni möjlighet till ett kort samtal?' +
            '\n\nVänliga hälsningar,\nBoxon')
    return {'subject': f'En fråga om förpackningar hos {company}', 'body': body}


class PublicPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.ignored += 1
        if tag == 'a':
            href = dict(attrs).get('href', '')
            if len(href) < 2048:
                self.links.append(href)
        if tag in ('p', 'div', 'li', 'br', 'section'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.ignored = max(0, self.ignored - 1)
        if tag in ('p', 'div', 'li', 'section'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def public_url(url):
    p = urlsplit(url)
    if (p.scheme != 'https' or not p.hostname or p.username or p.password or
            p.port not in (None, 443) or len(url) > 2048 or any(ord(x) < 33 for x in url)):
        raise ValueError('Ange företagets publika HTTPS-webbplats utan inloggning eller särskild port.')
    return urlunsplit(('https', p.netloc, p.path or '/', p.query, ''))


def fetch_public(url, timeout=5):
    """Pin a validated public IP for the TCP connection; preserve TLS hostname checks.

    Do not use proxy environment variables, follow redirects here, or resolve twice.
    This prevents private IP targets and DNS rebinding, including redirects to LAN.
    """
    url = public_url(url)
    deadline = time.monotonic() + timeout
    p = urlsplit(url)
    addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
    def allowed(address):
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            return False
        if ip.version == 6 and (ip.ipv4_mapped or ip.sixtofour or ip.teredo or
                               ip in ipaddress.ip_network('64:ff9b::/96') or
                               ip in ipaddress.ip_network('64:ff9b:1::/48')):
            return False
        return True
    if not addresses or any(not allowed(a[4][0]) for a in addresses):
        raise ValueError('Webbplatsen måste ha en publik internetadress.')
    family, kind, proto, _, endpoint = addresses[0]

    def connect(address, timeout=timeout, source_address=None, **kwargs):
        sock = socket.socket(family, kind, proto)
        sock.settimeout(timeout)
        try:
            sock.connect(endpoint)
            return sock
        except Exception:
            sock.close()
            raise

    conn = http.client.HTTPSConnection(p.hostname, timeout=timeout, context=ssl.create_default_context())
    conn._create_connection = connect
    try:
        conn.request('GET', urlunsplit(('', '', p.path or '/', p.query, '')),
                     headers={'User-Agent': 'Noair-contact-research/1.0', 'Accept': 'text/html', 'Accept-Encoding': 'identity'})
        transport = conn.sock
        response = conn.getresponse()
        if response.status in (301, 302, 303, 307, 308):
            return {'redirect': urljoin(url, response.getheader('Location', ''))}
        if response.status != 200 or 'text/html' not in response.getheader('Content-Type', ''):
            raise ValueError('Kontaktinformationen kunde inte läsas från webbplatsen.')
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Webbplatsen svarade för långsamt.')
            transport.settimeout(remaining)
            chunk = response.read1(min(8192, 300_001-size))
            if not chunk:
                break
            size += len(chunk)
            if size > 300_000:
                raise ValueError('Webbsidan är för stor för automatisk kontaktsökning.')
            chunks.append(chunk)
        raw = b''.join(chunks)
        charset = response.headers.get_content_charset() or 'utf-8'
        return {'html': raw.decode(charset, errors='replace')}
    finally:
        conn.close()


def lookup_contacts(website, fetch=None):
    fetch = fetch or fetch_public
    website = public_url(website)
    host = urlsplit(website).hostname.removeprefix('www.')
    pending, visited, found = [website], set(), {}
    deadline = time.monotonic() + 22
    errors = 0
    while pending and len(visited) < 4 and time.monotonic() < deadline:
        url = public_url(pending.pop(0))
        if url in visited or urlsplit(url).hostname.removeprefix('www.') != host:
            continue
        visited.add(url)
        try:
            result = fetch(url, timeout=min(5, max(1, deadline-time.monotonic())))
            if 'redirect' in result:
                target = public_url(result['redirect'])
                if urlsplit(target).hostname.removeprefix('www.') == host:
                    pending.insert(0, target)
                continue
            page = PublicPage(); page.feed(result['html'])
            lines = [' '.join(line.split())[:500] for line in ''.join(page.parts).splitlines() if line.strip()]
            emails = set(EMAIL.findall('\n'.join(lines)))
            emails.update(unquote(h[7:]).split('?')[0] for h in page.links if h.lower().startswith('mailto:'))
            for email in sorted(emails):
                if not valid_email(email):
                    continue
                context = next((line for line in lines if email in line), '')[:300]
                candidate = {'email': email, 'source': url, 'context': context,
                             'priority': bool(ROLE.search(context)), 'name': '', 'role': '', 'checked_at': time.strftime('%Y-%m-%d', time.gmtime())}
                if email.lower() not in found or candidate['priority']:
                    found[email.lower()] = candidate
            for href in page.links:
                if not re.search(r'kontakt|contact|team|inkop|inköp|purchase|procurement', href, re.I):
                    continue
                target = urljoin(url, href)
                try:
                    target = public_url(target)
                    if urlsplit(target).hostname.removeprefix('www.') == host:
                        pending.append(target)
                except ValueError:
                    pass
        except (ValueError, OSError, http.client.HTTPException, LookupError):
            errors += 1
    contacts = sorted(found.values(), key=lambda x: not x['priority'])[:20]
    if not contacts:
        message = 'Ingen offentlig e-postadress hittades. Lägg till en verifierad kontakt manuellt.'
    else:
        message = 'Offentliga kontaktförslag hittades. Kontrollera företag och inköpsansvar mot källan.'
    if errors:
        message += ' En eller flera sidor kunde inte läsas.'
    return {'contacts': contacts, 'lookup_note': message}


class DeliveryUncertain(Exception):
    pass


class DeliveryRejected(Exception):
    """Adapter guarantees that the provider did not accept this message."""
    pass


def mail_configured(config):
    # The eMarketeer account/API connection is deliberately deferred. An adapter
    # is injected by the server integration, never supplied by an HTTP request.
    return bool(config.get('mail_enabled') and callable(config.get('delivery_adapter')) and
                valid_email(config.get('mail_from')))


def send_message(config, draft):
    if not mail_configured(config):
        raise ValueError('eMarketeer är inte anslutet. Meddelandet ligger kvar i kön.')
    # Contract for the future eMarketeer adapter: return after confirmed acceptance;
    # raise DeliveryUncertain if acceptance may have happened. No automatic retries.
    config['delivery_adapter']({
        'from_email': config['mail_from'], 'from_name': config.get('mail_from_name', 'Boxon'),
        'to_email': draft['recipient_email'], 'subject': draft['subject'], 'body': draft['body'],
        'idempotency_key': hashlib.sha256(draft['report_id'].encode()).hexdigest(),
    })
