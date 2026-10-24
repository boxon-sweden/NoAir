"""Build a self-contained offline demo, including the supplied hero illustration.
Demo reports live only in page memory; no analytics or external font requests.
"""
from pathlib import Path
import base64, re
ROOT=Path(__file__).resolve().parent

def build(target=None):
    html=(ROOT/'static/index.html').read_text(encoding='utf-8')
    # Attribute order is immaterial (the markup is serialized by BeautifulSoup).
    def inline_css(match):
        attrs=match.group(0)
        href=re.search(r'href="(/static/[^\"]+\.css)"',attrs)
        if not href:return attrs
        css=(ROOT/href.group(1).lstrip('/')).read_text(encoding='utf-8')
        return '<style>\n'+css+'\n</style>'
    html=re.sub(r'<link\b[^>]*>',inline_css,html)
    html=re.sub(r'<script\b[^>]*src="/static/app\.js"[^>]*>\s*</script>','',html)
    hero=base64.b64encode((ROOT/'static/parcel-hero.webp').read_bytes()).decode('ascii')
    html=html.replace('/static/parcel-hero.webp','data:image/webp;base64,'+hero)
    js=(ROOT/'static/app.js').read_text(encoding='utf-8')
    html=html.replace('data-demo="false"','data-demo="true"')
    html=html.replace('</body>','<script>\n'+js+'\n</script>\n</body>')
    target=Path(target) if target else ROOT/'noair-forhandsvisning.html'
    target.write_text(html,encoding='utf-8')
    return target

if __name__=='__main__':print(build())
