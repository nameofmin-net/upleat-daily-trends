#!/usr/bin/env python3
"""UPLEAT 데일리 트렌드 — 고정 매체 RSS 후보 수집기.

리서치 루틴이 [1-0단계]에서 실행한다. FEEDS의 RSS/Atom을 읽어 오늘(KST) 기준
최근 30일 이내 글만 /tmp/rss_candidates.json 에 저장하고 한 줄씩 출력한다.
매체를 추가·삭제하려면 FEEDS만 고치면 된다 (페이지 공지의 NOTICE_SOURCES도 함께).
"""
import urllib.request, re, email.utils, datetime, html, json, concurrent.futures as cf
KST = datetime.timezone(datetime.timedelta(hours=9))
TODAY = datetime.datetime.now(KST).date()
CUTOFF = TODAY - datetime.timedelta(days=30)
FEEDS = [
 ("해외","ux","NN/g","https://www.nngroup.com/feed/rss/"),
 ("해외","ux","Baymard","https://baymard.com/blog.atom"),
 ("해외","ux","MeasuringU","https://measuringu.com/feed/"),
 ("해외","ux","Smashing Magazine","https://www.smashingmagazine.com/feed/"),
 ("해외","ux","UX Collective","https://uxdesign.cc/feed"),
 ("해외","ux","UX Planet","https://uxplanet.org/feed"),
 ("해외","design","Figma","https://www.figma.com/blog/feed/atom.xml"),
 ("해외","design","Apple Developer","https://developer.apple.com/news/rss/news.rss"),
 ("해외","design","Fast Company","https://www.fastcompany.com/co-design/rss"),
 ("해외","design","Dezeen","https://www.dezeen.com/design/feed/"),
 ("해외","design","Creative Bloq","https://www.creativebloq.com/feeds/all"),
 ("해외","design","Sidebar","https://sidebar.io/feed.xml"),
 ("해외","design","Muzli","https://medium.muz.li/feed"),
 ("해외","ai","OpenAI","https://openai.com/news/rss.xml"),
 ("해외","ai","Google AI","https://blog.google/technology/ai/rss/"),
 ("해외","ai","MIT Technology Review","https://www.technologyreview.com/feed/"),
 ("해외","ai","The Verge","https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
 ("해외","ai","TechCrunch","https://techcrunch.com/category/artificial-intelligence/feed/"),
 ("해외","biz","TechCrunch","https://techcrunch.com/feed/"),
 ("해외","biz","The Verge","https://www.theverge.com/rss/index.xml"),
 ("국내","ux","토스 테크","https://toss.tech/rss.xml"),
 ("국내","ux","카카오 테크","https://tech.kakao.com/feed/"),
 ("국내","ux","당근","https://medium.com/feed/daangn"),
 ("국내","ux","LY(라인)","https://techblog.lycorp.co.jp/ko/feed/index.xml"),
 ("국내","ux","뱅크샐러드","https://blog.banksalad.com/rss.xml"),
 ("국내","ux","무신사","https://medium.com/feed/musinsa-tech"),
 ("국내","ux","오픈서베이","https://blog.opensurvey.co.kr/feed/"),
 ("국내","ux","요즘IT","https://yozm.wishket.com/magazine/feed/"),
 ("국내","design","디자인프레스","https://rss.blog.naver.com/designpress2016.xml"),
 ("국내","design","월간 디자인","https://design.co.kr/feed/"),
 ("국내","design","디자인컴파스","https://designcompass.org/feed/"),
 ("국내","ai","AI타임스","https://www.aitimes.com/rss/allArticle.xml"),
 ("국내","ai","전자신문","https://rss.etnews.com/Section901.xml"),
 ("국내","ai","ZDNet Korea","https://feeds.feedburner.com/zdkorea"),
 ("국내","biz","바이라인네트워크","https://byline.network/feed/"),
 ("국내","biz","플래텀","https://platum.kr/feed"),
 ("국내","biz","벤처스퀘어","https://www.venturesquare.net/feed"),
 ("국내","biz","아웃스탠딩","https://outstanding.kr/feed"),
]
def txt(s):
    s = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', s or '', flags=re.S)
    return html.unescape(re.sub(r'<[^>]+>', '', s)).strip()
def pdate(s):
    s = txt(s)
    try: return email.utils.parsedate_to_datetime(s).astimezone(KST).date()
    except Exception:
        try: return datetime.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(KST).date()
        except Exception:
            try: return datetime.date.fromisoformat(s[:10])
            except Exception: return None
def fetch(f):
    region, cat, src, url = f
    try:
        x = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 RSS-Reader','Accept':'application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8'}), timeout=15).read().decode('utf-8','ignore')
    except Exception as e:
        return f, None, f"{type(e).__name__} {getattr(e,'code','')}"
    out = []
    for blk in re.findall(r'<(?:item|entry)[\s>].*?</(?:item|entry)>', x, re.S):
        t = re.search(r'<title[^>]*>(.*?)</title>', blk, re.S)
        l = (re.search(r'<link>(.*?)</link>', blk, re.S)
             or re.search(r'<link[^>]*rel=["\']alternate["\'][^>]*href=["\']([^"\']+)', blk)
             or re.search(r'<link(?![^>]*(?:enclosure|image/))[^>]*href=["\']([^"\']+)', blk)
             or re.search(r'<id>(https?://.*?)</id>', blk))
        d = re.search(r'<(pubDate|published|dc:date|updated)>(.*?)</\1>', blk, re.S)
        desc = re.search(r'<(description|summary)[^>]*>(.*?)</\1>', blk, re.S)
        dt = pdate(d.group(2)) if d else None
        if dt and (dt < CUTOFF or dt > TODAY): continue
        out.append({"region":region,"cat":cat,"source":src,"pubDate":dt.isoformat() if dt else None,
                    "title":txt(t.group(1)) if t else "","url":re.sub(r"\?source=rss[^&]*$", "", txt(l.group(1))) if l else "",
                    "summary":txt(desc.group(2))[:200] if desc else ""})
    return f, out, None
cands = []
PER_FEED = 15
with cf.ThreadPoolExecutor(12) as ex:
    for f, out, err in ex.map(fetch, FEEDS):
        if err: print(f"[피드 실패] {f[2]} ({f[3]}): {err}")
        else: cands += sorted(out, key=lambda c: c['pubDate'] or '', reverse=True)[:PER_FEED]
json.dump(cands, open('/tmp/rss_candidates.json','w'), ensure_ascii=False, indent=1)
print(f"오늘 {TODAY} / 발행 하한일 {CUTOFF} / 후보 {len(cands)}건 -> /tmp/rss_candidates.json")
for c in sorted(cands, key=lambda c:(c['region'],c['cat'],c['pubDate'] or ''), reverse=True):
    print(f"{c['region']}|{c['cat']}|{c['source']}|{c['pubDate'] or '날짜없음'}|{c['title'][:90]}|{c['url']}")
