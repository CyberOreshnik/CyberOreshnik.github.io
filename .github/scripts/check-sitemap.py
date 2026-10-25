"""Audit the existing published sitemap without rewriting site content."""
from pathlib import Path
import argparse, concurrent.futures, json, time, urllib.request, urllib.robotparser
from defusedxml import ElementTree as ET
from html.parser import HTMLParser
def require(condition, detail):
    if not condition:
        raise ValueError(str(detail))

SITE = 'https://cyberoreshnik.github.io/crsis47-author-website/'
SITEMAP = SITE + 'sitemap.xml'
LOCALES = ['en', 'fr', 'ht', 'es', 'pt-BR', 'pt-PT', 'ru', 'ar', 'zh-Hans', 'zh-Hant', 'ja', 'fa', 'he', 'tr']
ROUTES = ['', 'about/', 'books/', 'research/', 'research/methodology/', 'research/personal-security-investigator/', 'updates/', 'contact/', 'books/the-47-second-question/', 'books/the-machine-has-the-keys/', 'books/the-other-machine-has-keys-too/', 'books/when-the-evidence-changes/', 'books/the-cost-of-waiting/']
EXPECTED = {SITE + ('' if locale == 'en' else locale + '/') + route for locale in LOCALES for route in ROUTES}

class Head(HTMLParser):

    def __init__(self):
        super().__init__()
        self.canonicals = []
        self.robots = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs.get('href', ''))
        if tag == 'meta' and attrs.get('name', '').lower() in ('robots', 'googlebot'):
            self.robots.append(attrs.get('content', ''))

def check_html(body, url):
    h = Head()
    h.feed(body.decode('utf-8'))
    require(len(h.canonicals) == 1, (url, h.canonicals))
    require(h.canonicals[0].rstrip('/') == url.rstrip('/'), (url, h.canonicals))
    require(all(('noindex' not in x.lower() for x in h.robots)), (url, h.robots))

def check_xml(body):
    require(len(body) <= 4000000, 'Sitemap exceeds size limit')
    tree = ET.fromstring(body, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    require(tree.tag == '{http://www.sitemaps.org/schemas/sitemap/0.9}urlset', tree.tag)
    urls = [e.text for e in tree.findall('{*}url/{*}loc')]
    require(len(urls) == len(EXPECTED) and len(set(urls)) == len(EXPECTED), len(urls))
    require(set(urls) == EXPECTED, {'missing': sorted(EXPECTED - set(urls)), 'extra': sorted(set(urls) - EXPECTED)})
    return urls

class NoRedirect(urllib.request.HTTPRedirectHandler):

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch(url, agent):
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(urllib.request.Request(url, headers={'User-Agent': agent, 'Cache-Control': 'no-cache'}), timeout=30) as response:
        body = response.read()
        require(response.status == 200, (url, response.status))
        require(response.url == url, (url, response.url))
        require('noindex' not in response.headers.get('X-Robots-Tag', '').lower(), 'Audit condition failed')
        return (body, dict(response.headers))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--static-only', action='store_true')
    parser.add_argument('--root', default='crsis47-author-website')
    args = parser.parse_args()
    root = Path(args.root)
    original = (root / 'sitemap.xml').read_bytes()
    urls = check_xml(original)
    for url in urls:
        check_html((root / url[len(SITE):] / 'index.html').read_bytes(), url)
    print('PASS static: valid UTF-8 XML; 182 unique intended URLs; 14 languages; all canonical pages match; no noindex', flush=True)
    if args.static_only:
        return
    normal = 'CRSIS47-Sitemap-Diagnostic/1.0'
    bot = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
    for agent in (normal, bot):
        for attempt in range(36):
            try:
                robots, headers = fetch('https://cyberoreshnik.github.io/robots.txt', agent)
                text = robots.decode('utf-8')
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(text.splitlines())
                require(SITEMAP in (rp.site_maps() or []), text)
                require(all((rp.can_fetch('Googlebot', url) for url in urls + [SITEMAP])), 'Audit condition failed')
                break
            except Exception:
                if attempt == 35:
                    raise
                time.sleep(5)
        body, headers = fetch(SITEMAP, agent)
        require(body == original, 'Live sitemap differs from committed XML')
        check_xml(body)
        content_type = next((v for k, v in headers.items() if k.lower() == 'content-type'), '')
        require('xml' in content_type.lower(), content_type)
        print(json.dumps({'sitemap': SITEMAP, 'userAgent': agent, 'httpStatus': 200, 'redirects': 0, 'bytes': len(body), 'urls': len(urls), 'headers': headers, 'rootRobotsAdvertisesSitemap': True, 'robotsAllowsAllUrls': True}), flush=True)

    def page(url):
        body, headers = fetch(url, bot)
        check_html(body, url)
        return url
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(page, urls))
    print(f'PASS live: {len(results)} canonical pages HTTP 200 without redirects, authentication or noindex; Googlebot user-agent tested, not an authenticated Google crawl confirmation', flush=True)
if __name__ == '__main__':
    main()
