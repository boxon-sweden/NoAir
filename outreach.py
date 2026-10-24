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
from urllib.parse import urlsplit, urlunsplit

EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}")
LABELS = {'air': 'mycket tomrum', 'filler': 'mycket fyllnadsmaterial', 'oversized': 'en stor låda i förhållande till innehållet', 'protection': 'frågor om produktskyddet', 'other': 'förpackningens utformning'}
ROLE = re.compile(r'inköp|emballage|förpackning|packaging|procurement|purchasing|supply chain|logistik', re.I)


def valid_email(value):
    return isinstance(value, str) and len(value) <= 254 and EMAIL.fullmatch(value) is not None


# Only product names from this vocabulary enter drafts automatically. Arbitrary
# customer text, contact details and image contents remain private.
PRODUCTS = [
    (r'hörlurar(?:na)?', 'hörlurar'), (r'headset(?:et)?', 'ett headset'),
    (r'laddare(?:n)?', 'en laddare'), (r'mobilskal(?:et)?', 'ett mobilskal'),
    (r'tangentbord(?:et)?', 'ett tangentbord'), (r'datormus(?:en)?', 'en datormus'),
    (r'kab(?:el|eln|lar|larna)', 'kablar'), (r'skor(?:na)?', 'skor'),
    (r'kläder(?:na)?', 'kläder'), (r'tröj(?:a|an|or|orna)', 'en tröja'),
    (r'bok(?:en)?|böcker(?:na)?', 'böcker'),
]


def product_from_text(comment):
    comment = re.sub(r'\S+@\S+|https?://\S+', lambda m: ' '*len(m.group()), comment, flags=re.I)
    candidates = []
    for pattern, label in PRODUCTS:
        for match in re.finditer(r'(?<!\w)(?:'+pattern+r')(?!\w)', comment, re.I):
            # Be conservative about negations and hypothetical comparisons.
            sentence_start = max(comment.rfind(mark, 0, match.start()) for mark in '.!?\n') + 1
            prefix = comment[sentence_start:match.start()]
            if re.search(r'\b(inte|ingen|inget|inga|istället för|i stället för|som om|till exempel|exempelvis|skulle|kunde|kanske)\b', prefix, re.I):
                continue
            candidates.append((match.start(), label))
    return min(candidates)[1] if candidates else ''


def draft_for(report, variant=0):
    """First-contact sales pitch based on attributed, report-specific observations."""
    company = re.sub(r'[\r\n\x00-\x1f]', ' ', report['company']).strip()
    selected = set(report['issues'])
    product = product_from_text(report.get('comment', ''))
    category = {'Elektronik':'elektronik', 'Kläder & skor':'kläder eller skor',
                'Hem & inredning':'hem- och inredningsprodukter',
                'Sport & fritid':'sport- och fritidsprodukter'}.get(report.get('category', ''), '')
    delivery = 'en leverans med '+product if product else ('en leverans av '+category if category else 'en leverans')
    observations = []
    if 'oversized' in selected:
        observations.append('att lådan var stor i förhållande till innehållet')
    if 'air' in selected:
        observations.append('att det fanns mycket tomrum i paketet')
    if 'filler' in selected:
        observations.append('att det användes mycket fyllnadsmaterial')
    if 'protection' in selected:
        observations.append('att produkten inte upplevdes vara tillräckligt skyddad')
    observation = ' och '.join(observations[:2]) if observations else 'att förpackningen kunde vara bättre anpassad till innehållet'
    insight = (f'Via Noair, Boxons initiativ för att fånga upp konsumenters leveransupplevelser, '
               f'har vi fått en rapport från en av era kunder om {delivery} från {company}. '
               f'Kunden beskriver {observation}.')
    if 'protection' in selected:
        proposal = 'en lösning med bättre passform och anpassad stötdämpning, där vi utvärderar skyddet för produkten'
    elif selected & {'air', 'oversized'}:
        proposal = 'ett mindre lådformat och en anpassad insats, med rätt skydd för innehållet'
    elif 'filler' in selected:
        proposal = 'bättre passform och en anpassad insats som kan minska behovet av fyllnadsmaterial'
    else:
        proposal = 'ett mer anpassat format, material och produktskydd'
    expertise = 'Vi på Boxon är specialister på att skräddarsy förpackningar efter produkten och hur den ska levereras.'
    offer = f'I det här fallet skulle vi vilja undersöka {proposal}.'
    value = 'Målet är en mer genomtänkt uppackning för kunden och mindre onödigt emballage för er.'
    cost = 'Kundunikt behöver inte bli dyrt. Vi jämför gärna ett anpassat alternativ med dagens lösning, både i funktion och kostnad.'
    meeting = 'Har du 15 minuter nästa vecka? Jag visar gärna hur vi skulle ta oss an just den här leveransen och undersöka om vi kan erbjuda er en bättre lösning.'
    referral = 'Om någon annan ansvarar för emballageinköp hos er får du gärna hänvisa mig rätt.'
    variants = [
        {'subject': f'En kundinsikt om era förpackningar, {company}',
         'body': f'Hej!\n\n{insight}\n\n{expertise} {offer} {value}\n\n{cost}\n\n{meeting}\n\n{referral}'},
        {'subject': f'Kan nästa paket från {company} ge ett bättre intryck?',
         'body': f'Hej!\n\nEn bra produkt förtjänar en leverans som känns lika genomtänkt. {insight}\n\n{expertise} {offer} Det kan vara en möjlighet att förbättra kundupplevelsen redan när paketet öppnas.\n\n{cost}\n\nKan vi boka ett kort möte på 15 minuter nästa vecka och titta på vad Boxon skulle kunna göra för er?\n\n{referral}'},
        {'subject': f'15 minuter om ett mer anpassat paket hos {company}?',
         'body': f'Hej!\n\n{insight}\n\nJag hör av mig från Boxon, där vi hjälper företag med kundunika förpackningslösningar. {offer} Ambitionen är att göra förpackningen till en bättre del av kundupplevelsen.\n\nSkräddarsytt behöver inte betyda en dyrare lösning. Låt oss börja med att se vad som är möjligt för just er produkt och era volymer.\n\nPassar ett första samtal på 15 minuter nästa vecka? Då kan vi utgå från den här leveransen och prata om ett konkret alternativ från Boxon.\n\n{referral}'},
    ]
    result = variants[variant % len(variants)].copy()
    result['body'] += '\n\nVänliga hälsningar,\nMarcus Gustafsson\nBoxon'
    return result


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
        'idempotency_key': hashlib.sha256((draft['report_id']+'|'+draft['recipient_email'].casefold()).encode()).hexdigest(),
    })


def normalize_recipients(raw, legacy=None):
    """Validate selected/manual contacts without guessing missing email addresses."""
    if raw is None:raw=[]
    if not isinstance(raw,list) or len(raw)>30:
        raise ValueError('Välj högst 30 kontaktpersoner.')
    if not raw and legacy and any(legacy.get(k) for k in ('email','name','role')):
        raw=[legacy]
    recipients=[];seen=set()
    for item in raw:
        if not isinstance(item,dict):raise ValueError('Kontrollera kontaktpersonerna.')
        contact={}
        for field,limit in {'name':160,'role':160,'email':254,'source_url':2048}.items():
            value=item.get(field,'')
            if not isinstance(value,str) or len(value)>limit or any(c in value for c in '\r\n\x00'):
                raise ValueError('Kontrollera kontaktpersonernas uppgifter.')
            contact[field]=value.strip()
        if not any(contact.values()):continue
        if contact['email'] and not valid_email(contact['email']):raise ValueError('En kontaktperson har en ogiltig e-postadress.')
        if contact['source_url']:contact['source_url']=public_url(contact['source_url'])
        key=contact['email'].casefold() if contact['email'] else '|'.join(contact.values()).casefold()
        if key in seen:continue
        seen.add(key);recipients.append(contact)
    return recipients


def delivery_state(deliveries, recipients):
    states=[deliveries.get(r['email'].casefold(),{}).get('state','pending') for r in recipients]
    if states and all(s=='sent' for s in states):return 'sent'
    if any(s in {'sending','uncertain'} for s in states):return 'uncertain'
    return 'failed'
