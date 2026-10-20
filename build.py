#!/usr/bin/env python3
"""Static site generator for the UPLEAT daily trend archive.

Reads data/YYYY-MM-DD.json files (each {"intl": {...}, "domestic": {...}},
day-grouped with categories of articles) and flattens them into individual
article posts (a blog/Brunch-style model, not a day-bundle model):
  - index.html: single reverse-chronological feed (search, category pills,
    load-more), one row per article
  - articles/{date}-{i|d}-{cat}-{n}.html: one permalink page per article

Articles whose source JSON marks them `duplicate: true` (same URL already
published within the rolling 7-day dedup window) are skipped entirely —
they are not given their own post, since that would just republish the same
URL as a "new" entry.

Design system + interaction patterns adapted from wiseapp.co.kr/insight
(search box, pill filters, "popular" side rail, load-more button, floating
scroll-top, full-bleed hero + white content card detail-page pattern).

Usage: python3 build.py
"""
import json
import glob
import os
import re
import html as htmllib

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
ARTICLES_DIR = os.path.join(ROOT, "articles")

CATEGORY_ORDER = ["ai", "ux", "design", "biz"]
CATEGORY_LABEL = {
    "ai": "AI",
    "ux": "UX",
    "design": "DESIGN",
    "biz": "TECH & BIZ",
}
CATEGORY_COLOR = {
    "ai": "#8F8CF5",
    "ux": "#F2A93B",
    "design": "#F2767A",
    "biz": "#2BC9AE",
}
CATEGORY_EMOJI = {
    "ai": "🧠",
    "ux": "🧭",
    "design": "🎨",
    "biz": "📈",
}
GRADIENTS = [
    "linear-gradient(135deg,#8F8CF5,#6A63E8)",
    "linear-gradient(135deg,#F2A93B,#F08424)",
    "linear-gradient(135deg,#F2767A,#E8515E)",
    "linear-gradient(135deg,#2BC9AE,#17AE98)",
]
CATEGORY_GRADIENT = dict(zip(CATEGORY_ORDER, GRADIENTS))

STYLE = """
:root{
  --accent:#1868E0;
  --accent-dim:#EAF2FE;
  --ink:#16181D;
  --sub:#656973;
  --sub2:#8B92A0;
  --line:#E9EBEF;
  --bg:#F3F5F7;
  --card:#FFFFFF;
  --shadow:0 4px 10px rgba(16,24,40,.07), 0 1px 2px rgba(16,24,40,.04);
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{
  background:var(--bg);
  color:var(--ink);
  font-family:"Pretendard","Apple SD Gothic Neo",-apple-system,BlinkMacSystemFont,sans-serif;
  line-height:1.6;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1100px;margin:0 auto;padding:36px 20px 80px;}
a{color:inherit;text-decoration:none;}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:14px 0;border-bottom:1px solid var(--line);margin-bottom:28px;}
.brand{font-weight:800;letter-spacing:.02em;font-size:15px;color:var(--ink);}
.brand a{color:inherit;}
.topbar .gh{font-size:13px;color:var(--sub);}
.topbar .gh:hover{color:var(--accent);}

header.site{margin-bottom:22px;}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);margin:0 0 8px;}
h1{font-size:28px;font-weight:800;margin:0 0 10px;letter-spacing:-.01em;}
.note{font-size:13px;color:var(--sub);background:var(--accent-dim);border-left:3px solid var(--accent);padding:12px 14px;border-radius:0 8px 8px 0;margin:16px 0 0;}
.back{display:inline-block;margin-bottom:20px;font-size:14px;font-weight:600;color:var(--accent);}
.back:hover{text-decoration:underline;}

/* search + pill filters row */
.filter-row{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin:18px 0 26px;}
.search-box{position:relative;max-width:320px;flex:1;min-width:200px;}
.search-box input{width:100%;padding:10px 14px 10px 36px;border:1px solid var(--line);border-radius:999px;font-family:inherit;font-size:13.5px;background:var(--card);color:var(--ink);}
.search-box input:focus{outline:none;border-color:var(--accent);}
.search-box::before{content:"🔍";position:absolute;left:13px;top:50%;transform:translateY(-50%);font-size:12px;opacity:.5;}
.pill-row{display:flex;gap:8px;flex-wrap:wrap;}
.pill-btn{appearance:none;cursor:pointer;font-family:inherit;border:1px solid var(--line);background:var(--card);color:var(--sub);font-size:13px;font-weight:600;padding:7px 14px;border-radius:999px;transition:all .12s ease;}
.pill-btn.active{background:var(--ink);color:#fff;border-color:var(--ink);}
.pill-btn:hover:not(.active){border-color:var(--sub2);}

/* layout: grid + aside */
.content-layout{display:grid;grid-template-columns:1fr 272px;gap:24px;align-items:start;}
@media (max-width:860px){.content-layout{grid-template-columns:1fr;}}

/* article feed — single reverse-chronological timeline */
.feed-list{background:var(--card);border-radius:12px;box-shadow:var(--shadow);padding:4px 22px;}
.feed-item{display:block;padding:20px 0;border-top:1px solid var(--line);}
.feed-item:first-child{border-top:none;}
.feed-meta{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--sub2);margin-bottom:6px;}
.feed-cat{font-weight:800;}
.feed-dot{opacity:.6;}
.feed-title{font-size:16px;font-weight:700;margin:0 0 6px;letter-spacing:-.01em;}
.feed-item:hover .feed-title{color:var(--accent);}
.feed-insight{font-size:13.5px;color:var(--sub);line-height:1.6;margin:0;}
.feed-insight b{color:var(--ink);}
.hidden-initial{display:none;}

.loadmore-wrap{text-align:center;margin-top:24px;}
.loadmore-btn{appearance:none;cursor:pointer;font-family:inherit;background:var(--card);border:1px solid var(--line);color:var(--sub);font-weight:700;font-size:14px;padding:13px 0;width:100%;border-radius:10px;box-shadow:var(--shadow);}
.loadmore-btn:hover{border-color:var(--accent);color:var(--accent);}
.no-results{font-size:14px;color:var(--sub);padding:40px 0;text-align:center;}

aside.rail{background:var(--card);border-radius:12px;box-shadow:var(--shadow);padding:18px;}
aside.rail h3{font-size:14px;margin:0 0 14px;font-weight:800;}
.rail-item{display:flex;gap:10px;padding:10px 0;border-top:1px solid var(--line);}
.rail-item:first-of-type{border-top:none;padding-top:0;}
.rail-text{font-size:12.5px;color:var(--ink);line-height:1.5;}
.rail-text b{color:var(--accent);}
.rail-date{display:block;font-size:11px;color:var(--sub2);margin-top:2px;}

.scrolltop{position:fixed;right:24px;bottom:24px;width:44px;height:44px;border-radius:50%;background:var(--ink);color:#fff;border:none;cursor:pointer;font-size:16px;box-shadow:0 6px 16px rgba(0,0,0,.2);opacity:0;pointer-events:none;transition:opacity .2s ease, transform .2s ease;z-index:50;}
.scrolltop.show{opacity:1;pointer-events:auto;}
.scrolltop:hover{transform:translateY(-2px);}

/* article detail page — full-bleed hero + contained content card (wiseapp detail-page pattern) */
.hero-cover{width:100%;height:220px;position:relative;overflow:hidden;}
.hero-inner{max-width:1100px;height:100%;margin:0 auto;padding:0 20px;position:relative;display:flex;align-items:center;justify-content:center;}
.hero-cover .hero-emoji{font-size:62px;opacity:.9;filter:drop-shadow(0 6px 14px rgba(0,0,0,.15));}
.hero-info{position:absolute;left:20px;bottom:20px;display:flex;align-items:center;gap:8px;}
.hero-tag{font-size:11px;font-weight:800;letter-spacing:.03em;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,.92);color:#16181D;}
.hero-date{font-size:13px;font-weight:700;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.3);}
.detail-card{position:relative;background:var(--card);border-radius:16px;box-shadow:var(--shadow);padding:28px 28px 30px;}
.detail-card > h1{font-size:23px;margin-bottom:10px;}
.src{font-size:12.5px;color:var(--sub);margin:0 0 18px;}
.insight{font-size:14.5px;color:#3D4250;line-height:1.7;padding-left:12px;border-left:2px solid var(--line);margin-bottom:22px;}
.insight b{color:var(--accent);}
.source-cta{display:inline-block;margin:0 0 6px;padding:11px 22px;background:var(--ink);color:#fff;border-radius:999px;font-size:13.5px;font-weight:700;}
.source-cta:hover{background:var(--accent);}
.tag-cloud{display:flex;flex-wrap:wrap;gap:8px;margin:26px 0 22px;padding-top:22px;border-top:1px solid var(--line);}
.tag-pill{font-size:12px;color:var(--sub);background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 13px;}
.detail-note{font-size:12.5px;color:var(--sub);background:#F7F8FA;border-radius:10px;padding:14px 16px;line-height:1.7;}

.daynav{display:flex;justify-content:space-between;align-items:center;margin:16px 0 28px;font-size:14px;font-weight:600;background:var(--card);border-radius:12px;box-shadow:var(--shadow);padding:16px 20px;}
.daynav a{color:var(--accent);}
.daynav .spacer{flex:1;}

.related-strip{margin-bottom:28px;}
.related-strip h3{font-size:14px;font-weight:800;margin:0 0 12px;}
.related-scroll{display:flex;gap:12px;overflow-x:auto;padding-bottom:4px;}
.related-tile{flex:0 0 auto;width:160px;background:var(--card);border-radius:12px;box-shadow:var(--shadow);overflow:hidden;display:block;}
.related-tile .rt-art{height:56px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:24px;}
.related-tile .rt-label{font-size:12px;font-weight:700;padding:8px 10px 10px;color:var(--ink);line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}

footer.site{margin-top:48px;font-size:12px;color:var(--sub);text-align:center;}
"""

SCROLLTOP_SCRIPT = """
<button class="scrolltop" id="scrolltop" aria-label="맨 위로">↑</button>
<script>
(function(){
  var btn = document.getElementById('scrolltop');
  window.addEventListener('scroll', function(){
    if (window.scrollY > 400) btn.classList.add('show'); else btn.classList.remove('show');
  });
  btn.addEventListener('click', function(){ window.scrollTo({top:0, behavior:'smooth'}); });
})();
</script>
"""

FEED_SCRIPT = """
<script>
(function(){
  var PAGE_SIZE = 12;
  var items = Array.prototype.slice.call(document.querySelectorAll('.feed-item'));
  var loadBtn = document.getElementById('loadMoreBtn');
  var noResults = document.getElementById('noResults');
  var searchInput = document.getElementById('searchInput');
  var pillBtns = Array.prototype.slice.call(document.querySelectorAll('.pill-btn'));

  var state = { cat: 'all', q: '', visible: PAGE_SIZE };

  function matches(item){
    if (state.cat !== 'all' && item.dataset.cat !== state.cat) return false;
    if (state.q && item.dataset.search.indexOf(state.q) === -1) return false;
    return true;
  }

  function render(){
    var shown = 0, matched = 0;
    items.forEach(function(item){
      var ok = matches(item);
      if (ok) matched++;
      var within = ok && shown < state.visible;
      item.style.display = ok ? '' : 'none';
      item.classList.toggle('hidden-initial', ok && !within);
      if (within) shown++;
    });
    loadBtn.style.display = (matched > state.visible) ? '' : 'none';
    noResults.style.display = (matched === 0) ? '' : 'none';
  }

  searchInput.addEventListener('input', function(){
    state.q = this.value.trim().toLowerCase();
    state.visible = PAGE_SIZE;
    render();
  });
  pillBtns.forEach(function(btn){
    btn.addEventListener('click', function(){
      pillBtns.forEach(function(b){ b.classList.remove('active'); });
      btn.classList.add('active');
      state.cat = btn.dataset.cat;
      state.visible = PAGE_SIZE;
      render();
    });
  });
  loadBtn.addEventListener('click', function(){
    state.visible += PAGE_SIZE;
    render();
  });

  render();
})();
</script>
"""

HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css">
<style>{style}</style>
</head>
<body>
<div class="topbar wrap" style="padding-top:0;padding-bottom:0;max-width:1100px;">
  <div class="brand"><a href="{root_prefix}index.html">UPLEAT · Daily Trend Archive</a></div>
  <a class="gh" href="https://github.com/nameofmin-net/upleat-daily-trends" target="_blank" rel="noopener">GitHub ↗</a>
</div>
"""

FOOT = """
{scrolltop}
</body>
</html>
"""

FOOTER_HTML = '<footer class="site">UPLEAT &middot; Daily Trend Archive &middot; 구조/디자인 레퍼런스: wiseapp.co.kr/insight &amp; magazine-hd.kr</footer>'


def esc(s):
    return htmllib.escape(s, quote=False) if s else ""


def strip_tags(s):
    return re.sub(r"</?b>", "", s or "")


def preview_text(text_html, limit=100):
    text = strip_tags(text_html)
    if len(text) > limit:
        text = text[:limit] + "…"
    return esc(text)


def build_articles(days):
    """Flatten day-grouped data into individual non-duplicate articles, newest first."""
    articles = []
    for d in days:
        date = d["intl"]["date"]
        date_label = d["intl"]["dateLabel"]
        for region_key, region_label in (("intl", "해외"), ("domestic", "국내")):
            for cat in d[region_key]["categories"]:
                kept_idx = 0
                for item in cat["items"]:
                    if item.get("duplicate"):
                        continue
                    kept_idx += 1
                    slug = f"{date}-{'i' if region_key == 'intl' else 'd'}-{cat['key']}-{kept_idx}"
                    articles.append({
                        "id": slug,
                        "date": date,
                        "dateLabel": date_label,
                        "region_key": region_key,
                        "region": region_label,
                        "cat_key": cat["key"],
                        "cat_label": cat["label"],
                        "title": item["title"],
                        "url": item["url"],
                        "source": item.get("source", ""),
                        "pubDate": item.get("pubDate"),
                        "insight": item["insight"],
                    })
    return articles


def render_feed_item(a):
    color = CATEGORY_COLOR[a["cat_key"]]
    emoji = "🌐" if a["region_key"] == "intl" else "🇰🇷"
    short_date = a["date"][5:].replace("-", ".")
    search_bits = esc(" ".join([a["title"], strip_tags(a["insight"]), a["source"], a["dateLabel"]])).lower()
    return f'''<article class="feed-item" data-cat="{a['cat_key']}" data-search="{search_bits}">
<a class="feed-link" href="articles/{a['id']}.html">
  <div class="feed-meta"><span>{emoji}</span><span class="feed-cat" style="color:{color}">{a['cat_label']}</span><span class="feed-dot">&middot;</span><span class="feed-date">{short_date}</span><span class="feed-dot">&middot;</span><span class="feed-src">{esc(a['source'])}</span></div>
  <h2 class="feed-title">{a['title']}</h2>
  <p class="feed-insight">{preview_text(a['insight'])}</p>
</a>
</article>'''


def render_rail(articles, limit=5):
    items = []
    for a in articles[:limit]:
        m = re.search(r"<b>(.*?)</b>", a["insight"])
        phrase = esc(m.group(1)) if m else esc(strip_tags(a["insight"])[:30])
        items.append(f'''<div class="rail-item">
<a href="articles/{a['id']}.html" class="rail-text"><b>{phrase}</b><span class="rail-date">{a['dateLabel']}</span></a>
</div>''')
    return f'''<aside class="rail">
<h3>최근 핵심 인사이트</h3>
{"".join(items)}
</aside>'''


def pick_related(articles, idx, limit=4):
    current = articles[idx]
    candidates = sorted(
        (j for j in range(len(articles)) if j != idx and articles[j]["cat_key"] == current["cat_key"]),
        key=lambda j: abs(j - idx),
    )[:limit]
    picked = [articles[j] for j in candidates]
    picked.sort(key=lambda a: (a["date"], a["id"]), reverse=True)
    return picked


def render_article_page(a, prev_a, next_a, related):
    gradient = CATEGORY_GRADIENT[a["cat_key"]]
    emoji = CATEGORY_EMOJI.get(a["cat_key"], "📡")

    tags = [a["region"], a["cat_label"]]
    if a["source"]:
        tags.append(a["source"])
    tags_html = "".join(f'<span class="tag-pill">#{esc(t)}</span>' for t in tags)

    meta_line = esc(a["source"])
    if a.get("pubDate"):
        meta_line += f" &middot; {a['pubDate']}"

    nav_prev = f'<a href="{prev_a["id"]}.html">← 이전 글</a>' if prev_a else '<span></span>'
    nav_next = f'<a href="{next_a["id"]}.html">다음 글 →</a>' if next_a else '<span></span>'

    related_tiles = []
    for r in related:
        rcolor = CATEGORY_COLOR[r["cat_key"]]
        rtitle = r["title"]
        related_tiles.append(f'''<a class="related-tile" href="{r['id']}.html">
<div class="rt-art" style="background:{rcolor}">{CATEGORY_EMOJI.get(r['cat_key'], '📡')}</div>
<div class="rt-label">{rtitle}</div>
</a>''')
    related_html = ""
    if related_tiles:
        related_html = f'''<div class="related-strip">
<h3>{a['cat_label']} 카테고리의 다른 글</h3>
<div class="related-scroll">{"".join(related_tiles)}</div>
</div>'''

    return f'''<div class="wrap" style="padding-bottom:0;">
<a class="back" href="../index.html">← 피드로</a>
</div>

<div class="hero-cover" style="background:{gradient}">
<div class="hero-inner">
<div class="hero-emoji">{emoji}</div>
<div class="hero-info"><span class="hero-tag">{a['region']} &middot; {a['cat_label']}</span><span class="hero-date">{a['dateLabel']}</span></div>
</div>
</div>

<div class="wrap" style="padding-top:28px;">
<div class="detail-card">
<h1>{a['title']}</h1>
<div class="src">{meta_line}</div>
<div class="insight">{a['insight']}</div>
<a class="source-cta" href="{a['url']}" target="_blank" rel="noopener">원문 보기 ↗</a>
<div class="tag-cloud">{tags_html}</div>
<div class="detail-note">이 글은 UPLEAT가 매일 새벽 자동 수집한 해외·국내 AI/UX/디자인/테크 트렌드 중 하나입니다. 올해 실제로 발행된 기사만 다루며, 지어낸 URL이나 날짜는 포함하지 않습니다. 직전 7일 내 동일 URL로 이미 글이 있으면 새로 만들지 않고 걸러냅니다.</div>
</div>

<div class="daynav">{nav_prev}<span class="spacer"></span>{nav_next}</div>
{related_html}
<a class="back" href="../index.html">← 피드로</a>
{FOOTER_HTML}
</div>'''


def build():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    days = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            days.append(json.load(f))
    days.sort(key=lambda d: d["intl"]["date"], reverse=True)

    articles = build_articles(days)

    os.makedirs(ARTICLES_DIR, exist_ok=True)

    # ---- index.html ----
    feed_html = "".join(render_feed_item(a) for a in articles)
    rail_html = render_rail(articles)

    pill_buttons = ['<button class="pill-btn active" data-cat="all">전체</button>']
    for key in CATEGORY_ORDER:
        pill_buttons.append(f'<button class="pill-btn" data-cat="{key}">{CATEGORY_LABEL[key]}</button>')

    index_body = f'''<div class="wrap">
<header class="site">
<p class="eyebrow">UPLEAT</p>
<h1>UPLEAT 데일리 트렌드 아카이브</h1>
<p class="note">이 사이트는 매일 자동 수집되는 UPLEAT 데일리 트렌드 리포트(노션 데이터베이스)를 기사 단위로 미러링하며, 새 글이 생성될 때마다 자동으로 업데이트됩니다. 총 {len(articles)}개의 글 수록.</p>
</header>

<div class="filter-row">
  <div class="search-box"><input id="searchInput" type="text" placeholder="날짜, 키워드, 기사 제목으로 검색"></div>
  <div class="pill-row">{"".join(pill_buttons)}</div>
</div>

<div class="content-layout">
  <div>
    <div class="feed-list" id="feedList">
{feed_html}
    </div>
    <div class="no-results" id="noResults" style="display:none">검색 결과가 없습니다.</div>
    <div class="loadmore-wrap"><button class="loadmore-btn" id="loadMoreBtn">더보기</button></div>
  </div>
  {rail_html}
</div>
{FOOTER_HTML}
</div>'''

    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(
            HEAD.format(title="UPLEAT 데일리 트렌드 아카이브", style=STYLE, root_prefix="")
            + index_body
            + FEED_SCRIPT
            + FOOT.format(scrolltop=SCROLLTOP_SCRIPT)
        )

    # ---- article pages ----
    for i, a in enumerate(articles):
        prev_a = articles[i + 1] if i + 1 < len(articles) else None  # older
        next_a = articles[i - 1] if i - 1 >= 0 else None  # newer
        related = pick_related(articles, i)
        body = render_article_page(a, prev_a, next_a, related)

        with open(os.path.join(ARTICLES_DIR, f"{a['id']}.html"), "w", encoding="utf-8") as f:
            f.write(
                HEAD.format(title=f"{a['title']} · UPLEAT Daily Brief", style=STYLE, root_prefix="../")
                + body
                + FOOT.format(scrolltop=SCROLLTOP_SCRIPT)
            )

    print(f"Built index.html + {len(articles)} article pages from {len(days)} day-files")


if __name__ == "__main__":
    build()
