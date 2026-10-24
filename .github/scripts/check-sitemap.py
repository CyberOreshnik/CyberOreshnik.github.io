"""Audit the existing published sitemap without rewriting site content."""
from pathlib import Path
import argparse,concurrent.futures,json,time,urllib.request,urllib.robotparser
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

SITE='https://cyberoreshnik.github.io/crsis47-author-website/'
SITEMAP=SITE+'sitemap.xml'
LOCALES=['en','fr','ht','es','pt-BR','pt-PT','ru','ar','zh-Hans','zh-Hant','ja','fa','he','tr']
ROUTES=['','about/','books/','research/','research/methodology/','research/personal-security-investigator/','updates/','contact/','books/the-47-second-question/','books/the-machine-has-the-keys/','books/the-other-machine-has-keys-too/','books/when-the-evidence-changes/']
EXPECTED={SITE+('' if locale=='en' else locale+'/')+route for locale in LOCALES for route in ROUTES}
class Head(HTMLParser):
 def __init__(self):super().__init__();self.canonicals=[];self.robots=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag=='link' and attrs.get('rel')=='canonical':self.canonicals.append(attrs.get('href',''))
  if tag=='meta' and attrs.get('name','').lower() in ('robots','googlebot'):self.robots.append(attrs.get('content',''))
def check_html(body,url):
 h=Head();h.feed(body.decode('utf-8'));assert len(h.canonicals)==1,(url,h.canonicals)
 assert h.canonicals[0].rstrip('/')==url.rstrip('/'),(url,h.canonicals)
 assert all('noindex' not in x.lower() for x in h.robots),(url,h.robots)
def check_xml(body):
 tree=ET.fromstring(body);assert tree.tag=='{http://www.sitemaps.org/schemas/sitemap/0.9}urlset',tree.tag
 urls=[e.text for e in tree.findall('{*}url/{*}loc')]
 assert len(urls)==168 and len(set(urls))==168,len(urls)
 assert set(urls)==EXPECTED,{'missing':sorted(EXPECTED-set(urls)),'extra':sorted(set(urls)-EXPECTED)}
 return urls
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
def fetch(url,agent):
 opener=urllib.request.build_opener(NoRedirect)
 with opener.open(urllib.request.Request(url,headers={'User-Agent':agent,'Cache-Control':'no-cache'}),timeout=30) as response:
  body=response.read();assert response.status==200,(url,response.status)
  assert response.url==url,(url,response.url)
  assert 'noindex' not in response.headers.get('X-Robots-Tag','').lower()
  return body,dict(response.headers)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--static-only',action='store_true');parser.add_argument('--root',default='crsis47-author-website');args=parser.parse_args()
 root=Path(args.root);original=(root/'sitemap.xml').read_bytes();urls=check_xml(original)
 for url in urls:check_html((root/url[len(SITE):]/'index.html').read_bytes(),url)
 print('PASS static: valid UTF-8 XML; 168 unique intended URLs; 14 languages; all canonical pages match; no noindex',flush=True)
 if args.static_only:return
 normal='CRSIS47-Sitemap-Diagnostic/1.0'
 bot='Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
 for agent in (normal,bot):
  for attempt in range(36):
   try:
    robots,headers=fetch('https://cyberoreshnik.github.io/robots.txt',agent);text=robots.decode('utf-8')
    rp=urllib.robotparser.RobotFileParser();rp.parse(text.splitlines());assert SITEMAP in (rp.site_maps() or []),text
    assert all(rp.can_fetch('Googlebot',url) for url in urls+[SITEMAP])
    break
   except Exception:
    if attempt==35:raise
    time.sleep(5)
  body,headers=fetch(SITEMAP,agent);assert body==original,'Live sitemap differs from committed XML';check_xml(body)
  content_type=next((v for k,v in headers.items() if k.lower()=='content-type'),'')
  assert 'xml' in content_type.lower(),content_type
  print(json.dumps({'sitemap':SITEMAP,'userAgent':agent,'httpStatus':200,'redirects':0,'bytes':len(body),'urls':168,'headers':headers,'rootRobotsAdvertisesSitemap':True,'robotsAllowsAllUrls':True}),flush=True)
 def page(url):
  body,headers=fetch(url,bot);check_html(body,url);return url
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(page,urls))
 print(f'PASS live: {len(results)} canonical pages HTTP 200 without redirects, authentication or noindex; Googlebot user-agent tested, not an authenticated Google crawl confirmation',flush=True)
if __name__=='__main__':main()
