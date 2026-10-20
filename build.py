#!/usr/bin/env python3
"""Static site generator for the UPLEAT daily trend archive.

Reads data/YYYY-MM-DD.json files (each {"intl": {...}, "domestic": {...}})
and renders:
  - index.html: card-grid archive (tabs, search, category pills, load-more)
  - days/YYYY-MM-DD.html: full day detail (해외 + 국내)

Design system + interaction patterns adapted from wiseapp.co.kr/insight
(card grid w/ colored header art, text tabs, pill content-type tabs,
search box, "popular" side rail, load-more button, floating scroll-top).

Usage: python3 build.py
"""
import json
import glob
import os
import re
import html as htmllib

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
DAYS_DIR = os.path.join(ROOT, "days")

CATEGORY_ORDER = ["ai", "ux", "design", "biz"]
CATEGORY_COLOR = {
    "ai": "#8F8CF5",
    "ux": "#F2A93B",
    "design": "#F2767A",
    "biz": "#2BC9AE",
}
GRADIENTS = [
    "linear-gradient(135deg,#8F8CF5,#6A63E8)",
    "linear-gradient(135deg,#F2A93B,#F08424)",
    "linear-gradient(135deg,#F2767A,#E8515E)",
    "linear-gradient(135deg,#2BC9AE,#17AE98)",
]

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

/* region text-tabs */
.tabs-row{display:flex;gap:22px;margin:26px 0 0;border-bottom:1px solid var(--line);}
.tab-btn{appearance:none;background:none;border:none;cursor:pointer;font-family:inherit;padding:10px 2px 12px;font-size:15px;font-weight:600;color:var(--sub2);border-bottom:2px solid transparent;margin-bottom:-1px;}
.tab-btn.active{color:var(--ink);border-bottom-color:var(--ink);}
.tab-btn:hover{color:var(--ink);}

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
.card-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;}
@media (max-width:860px){.card-grid{grid-template-columns:repeat(2,1fr);}}
@media (max-width:560px){.card-grid{grid-template-columns:1fr;}}

.day-card{display:block;background:var(--card);border-radius:12px;box-shadow:var(--shadow);overflow:hidden;transition:transform .15s ease, box-shadow .15s ease;}
.day-card:hover{transform:translateY(-3px);box-shadow:0 10px 24px rgba(16,24,40,.12);}
.day-card .art{height:88px;display:flex;align-items:center;justify-content:center;font-size:30px;position:relative;}
.day-card .art .badges{position:absolute;top:10px;left:10px;display:flex;gap:5px;}
.day-card .rbadge{font-size:10px;font-weight:800;padding:3px 8px;border-radius:999px;background:rgba(255,255,255,.92);color:#16181D;}
.day-card .body{padding:14px 16px 16px;}
.day-card .date{font-weight:700;font-size:15px;margin-bottom:5px;letter-spacing:-.01em;}
.day-card .preview{font-size:12.5px;color:var(--sub);line-height:1.55;min-height:38px;}
.day-card .preview b{color:var(--ink);font-weight:700;}
.day-card .meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;}
.cat-chip{font-size:10.5px;font-weight:700;padding:3px 8px;border-radius:999px;}
.hidden-initial{display:none;}

.loadmore-wrap{text-align:center;margin-top:24px;}
.loadmore-btn{appearance:none;cursor:pointer;font-family:inherit;background:var(--card);border:1px solid var(--line);color:var(--sub);font-weight:700;font-size:14px;padding:13px 0;width:100%;border-radius:10px;box-shadow:var(--shadow);}
.loadmore-btn:hover{border-color:var(--accent);color:var(--accent);}
.no-results{font-size:14px;color:var(--sub);padding:40px 0;text-align:center;}

aside.rail{background:var(--card);border-radius:12px;box-shadow:var(--shadow);padding:18px;}
aside.rail h3{font-size:14px;margin:0 0 14px;font-weight:800;}
.rail-item{display:flex;gap:10px;padding:10px 0;border-top:1px solid var(--line);}
.rail-item:first-of-type{border-top:none;padding-top:0;}
.rail-num{font-size:13px;font-weight:800;color:var(--accent);flex:0 0 auto;}
.rail-text{font-size:12.5px;color:var(--ink);line-height:1.5;}
.rail-text b{color:var(--accent);}
.rail-date{display:block;font-size:11px;color:var(--sub2);margin-top:2px;}

.scrolltop{position:fixed;right:24px;bottom:24px;width:44px;height:44px;border-radius:50%;background:var(--ink);color:#fff;border:none;cursor:pointer;font-size:16px;box-shadow:0 6px 16px rgba(0,0,0,.2);opacity:0;pointer-events:none;transition:opacity .2s ease, transform .2s ease;z-index:50;}
.scrolltop.show{opacity:1;pointer-events:auto;}
.scrolltop:hover{transform:translateY(-2px);}

/* day detail page — full-bleed hero + contained content card (wiseapp detail-page pattern) */
.hero-cover{width:100%;height:220px;position:relative;overflow:hidden;}
.hero-inner{max-width:1100px;height:100%;margin:0 auto;padding:0 20px;position:relative;display:flex;align-items:center;justify-content:center;}
.hero-cover .hero-emoji{font-size:62px;opacity:.9;filter:drop-shadow(0 6px 14px rgba(0,0,0,.15));}
.hero-info{position:absolute;left:20px;bottom:20px;display:flex;align-items:center;gap:8px;}
.hero-tag{font-size:11px;font-weight:800;letter-spacing:.03em;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,.92);color:#16181D;}
.hero-date{font-size:13px;font-weight:700;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.3);}
.detail-card{position:relative;background:var(--card);border-radius:16px;box-shadow:var(--shadow);padding:28px 28px 30px;}
.detail-card > h1{font-size:23px;margin-bottom:6px;}
.region-tabs{margin:18px 0 0;}
.tag-cloud{display:flex;flex-wrap:wrap;gap:8px;margin:28px 0 22px;padding-top:22px;border-top:1px solid var(--line);}
.tag-pill{font-size:12px;color:var(--sub);background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 13px;}
.detail-note{font-size:12.5px;color:var(--sub);background:#F7F8FA;border-radius:10px;padding:14px 16px;line-height:1.7;}

.daynav{display:flex;justify-content:space-between;align-items:center;margin:16px 0 28px;font-size:14px;font-weight:600;background:var(--card);border-radius:12px;box-shadow:var(--shadow);padding:16px 20px;}
.daynav a{color:var(--accent);}
.daynav .spacer{flex:1;}

.related-strip{margin-bottom:28px;}
.related-strip h3{font-size:14px;font-weight:800;margin:0 0 12px;}
.related-scroll{display:flex;gap:12px;overflow-x:auto;padding-bottom:4px;}
.related-tile{flex:0 0 auto;width:120px;background:var(--card);border-radius:12px;box-shadow:var(--shadow);overflow:hidden;display:block;}
.related-tile .rt-art{height:64px;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:18px;}
.related-tile .rt-label{font-size:11.5px;font-weight:700;padding:8px 10px 10px;color:var(--ink);}
.related-tile.current{outline:2px solid var(--accent);}

.takeaway{margin:18px 0 20px;padding:14px 16px;background:var(--accent-dim);border-radius:10px;font-size:14px;font-weight:600;}
.takeaway b{color:var(--accent);}
.region-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
@media (max-width:640px){.region-grid{grid-template-columns:1fr;}}
.cat-group{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:#fff;}
.cat-heading{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:800;letter-spacing:.02em;margin-bottom:10px;}
.cat-dot{width:8px;height:8px;border-radius:50%;flex:0 0 auto;}
.cat-count{color:var(--sub);font-weight:600;font-size:12px;}
.empty-note{font-size:13px;color:var(--sub);padding:2px 0 4px;}
.item{display:block;padding:12px 0;border-top:1px solid var(--line);}
.item:first-child{border-top:none;}
.item-title{font-size:14.5px;font-weight:700;color:var(--ink);}
.item-title:hover{color:var(--accent);}
.dup-badge{display:inline-block;font-size:10px;font-weight:800;color:#B42318;background:#FEE4E2;border-radius:999px;padding:1px 7px;margin-left:6px;vertical-align:middle;}
.src{font-size:12px;color:var(--sub);margin:3px 0 6px;}
.insight{font-size:13px;color:#3D4250;line-height:1.55;padding-left:10px;border-left:2px solid var(--line);}
.insight b{color:var(--accent);}
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

INDEX_SCRIPT = """
<script>
(function(){
  var PAGE_SIZE = 9;
  var cards = Array.prototype.slice.call(document.querySelectorAll('.day-card'));
  var grid = document.getElementById('cardGrid');
  var loadBtn = document.getElementById('loadMoreBtn');
  var noResults = document.getElementById('noResults');
  var searchInput = document.getElementById('searchInput');
  var regionTabs = Array.prototype.slice.call(document.querySelectorAll('.tab-btn'));
  var pillBtns = Array.prototype.slice.call(document.querySelectorAll('.pill-btn'));

  var state = { region: 'all', cat: 'all', q: '', visible: PAGE_SIZE };

  function matches(card){
    if (state.cat !== 'all' && card.dataset.cats.indexOf(state.cat) === -1) return false;
    if (state.q && card.dataset.search.indexOf(state.q) === -1) return false;
    return true;
  }

  function render(){
    var shown = 0, matched = 0;
    cards.forEach(function(card){
      var ok = matches(card);
      if (ok) matched++;
      var within = ok && shown < state.visible;
      card.style.display = ok ? '' : 'none';
      card.classList.toggle('hidden-initial', ok && !within);
      if (within) shown++;
      // region preview toggle
      var intlP = card.querySelector('.preview-intl');
      var domP = card.querySelector('.preview-domestic');
      if (intlP && domP) {
        if (state.region === '국내') { intlP.style.display = 'none'; domP.style.display = ''; }
        else if (state.region === '해외') { intlP.style.display = ''; domP.style.display = 'none'; }
        else { intlP.style.display = ''; domP.style.display = 'none'; }
      }
    });
    loadBtn.style.display = (matched > state.visible) ? '' : 'none';
    noResults.style.display = (matched === 0) ? '' : 'none';
  }

  searchInput.addEventListener('input', function(){
    state.q = this.value.trim().toLowerCase();
    state.visible = PAGE_SIZE;
    render();
  });
  regionTabs.forEach(function(btn){
    btn.addEventListener('click', function(){
      regionTabs.forEach(function(b){ b.classList.remove('active'); });
      btn.classList.add('active');
      state.region = btn.dataset.region;
      render();
    });
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

FOOTER_HTML = '<footer class="site">UPLEAT &middot; Daily Trend Archive &middot; 구조/디자인 레퍼런스: wiseapp.co.kr/insight</footer>'

DETAIL_SCRIPT = """
<script>
(function(){
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.region-tabs .tab-btn'));
  var panels = Array.prototype.slice.call(document.querySelectorAll('.region-panel'));
  tabs.forEach(function(btn){
    btn.addEventListener('click', function(){
      tabs.forEach(function(b){ b.classList.remove('active'); });
      btn.classList.add('active');
      var region = btn.dataset.region;
      panels.forEach(function(p){ p.style.display = (p.dataset.region === region) ? '' : 'none'; });
    });
  });
})();
</script>
"""


def esc(s):
    return htmllib.escape(s, quote=False) if s else ""


def strip_tags(s):
    return re.sub(r"</?b>", "", s or "")


def render_items(items):
    if not items:
        return '<div class="empty-note">2026년 발행 기사를 찾지 못했습니다.</div>'
    parts = []
    for item in items:
        dup = '<span class="dup-badge">중복</span>' if item.get("duplicate") else ""
        src = esc(item.get("source", ""))
        pub = item.get("pubDate")
        src_line = f"{src} &middot; {pub}" if pub else src
        parts.append(f'''<div class="item">
<a class="item-title" href="{item['url']}" target="_blank" rel="noopener">{item['title']}{dup}</a>
<div class="src">{src_line}</div>
<div class="insight">{item['insight']}</div>
</div>''')
    return "\n".join(parts)


def render_region_panel(day, region_key, active):
    groups = []
    for cat in day["categories"]:
        n = len(cat["items"])
        color = CATEGORY_COLOR[cat["key"]]
        groups.append(f'''<div class="cat-group">
<div class="cat-heading"><span class="cat-dot" style="background:{color}"></span><span style="color:{color}">{cat['label']}</span><span class="cat-count">({n})</span></div>
{render_items(cat['items'])}
</div>''')
    display = "" if active else "display:none"
    return f'''<div class="region-panel" data-region="{region_key}" style="{display}">
<div class="takeaway">{day['takeawayHtml']}</div>
<div class="region-grid">{"".join(groups)}</div>
</div>'''


def collect_tags(d):
    tags = ["해외", "국내"]
    sources = []
    for region_key in ("intl", "domestic"):
        for cat in d[region_key]["categories"]:
            if cat["items"]:
                tags.append(cat["label"])
            for item in cat["items"]:
                src = item.get("source")
                if src and src not in sources:
                    sources.append(src)
    # de-dup category labels while preserving order
    seen = []
    for t in tags:
        if t not in seen:
            seen.append(t)
    return seen + sources[:8]


def takeaway_preview(text_html, limit=68):
    text = strip_tags(text_html)
    if len(text) > limit:
        text = text[:limit] + "…"
    return esc(text)


def day_categories_present(d):
    present = set()
    for region_key in ("intl", "domestic"):
        for cat in d[region_key]["categories"]:
            if cat["items"]:
                present.add(cat["key"])
    return present


def render_day_card(d, idx):
    date = d["intl"]["date"]
    label = d["intl"]["dateLabel"]
    cats_present = day_categories_present(d)
    cats_attr = " ".join(sorted(cats_present))
    gradient = GRADIENTS[idx % len(GRADIENTS)]

    search_bits = [label]
    for region_key in ("intl", "domestic"):
        search_bits.append(strip_tags(d[region_key]["takeawayHtml"]))
        for cat in d[region_key]["categories"]:
            for item in cat["items"]:
                search_bits.append(item["title"])
    search_attr = esc(" ".join(search_bits)).lower()

    chips = []
    for key in CATEGORY_ORDER:
        if key in cats_present:
            color = CATEGORY_COLOR[key]
            lbl = next(c["label"] for c in d["intl"]["categories"] if c["key"] == key)
            chips.append(f'<span class="cat-chip" style="background:{color}22;color:{color}">{lbl}</span>')

    intl_preview = takeaway_preview(d["intl"]["takeawayHtml"])
    dom_preview = takeaway_preview(d["domestic"]["takeawayHtml"])

    return f'''<a class="day-card" href="days/{date}.html" data-cats="{cats_attr}" data-search="{search_attr}">
<div class="art" style="background:{gradient}">
  <div class="badges"><span class="rbadge">🌐 해외</span><span class="rbadge">🇰🇷 국내</span></div>
  <span>📡</span>
</div>
<div class="body">
  <div class="date">{label}</div>
  <div class="preview preview-intl"><b>해외</b> {intl_preview}</div>
  <div class="preview preview-domestic" style="display:none"><b>국내</b> {dom_preview}</div>
  <div class="meta">{"".join(chips)}</div>
</div>
</a>'''


def render_rail(days, limit=5):
    items = []
    for d in days[:limit]:
        m = re.search(r"<b>(.*?)</b>", d["intl"]["takeawayHtml"])
        phrase = esc(m.group(1)) if m else esc(strip_tags(d["intl"]["takeawayHtml"])[:30])
        items.append(f'''<div class="rail-item">
<a href="days/{d['intl']['date']}.html" class="rail-text"><b>{phrase}</b><span class="rail-date">{d['intl']['dateLabel']}</span></a>
</div>''')
    return f'''<aside class="rail">
<h3>최근 핵심 키워드</h3>
{"".join(items)}
</aside>'''


def build():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    days = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            days.append(json.load(f))
    days.sort(key=lambda d: d["intl"]["date"], reverse=True)
    dates = [d["intl"]["date"] for d in days]

    os.makedirs(DAYS_DIR, exist_ok=True)

    # ---- index.html ----
    cards_html = "".join(render_day_card(d, i) for i, d in enumerate(days))
    rail_html = render_rail(days)

    pill_buttons = ['<button class="pill-btn active" data-cat="all">전체</button>']
    if days:
        for key in CATEGORY_ORDER:
            lbl = next((c["label"] for c in days[0]["intl"]["categories"] if c["key"] == key), key.upper())
            pill_buttons.append(f'<button class="pill-btn" data-cat="{key}">{lbl}</button>')

    index_body = f'''<div class="wrap">
<header class="site">
<p class="eyebrow">UPLEAT</p>
<h1>UPLEAT 데일리 트렌드 아카이브</h1>
<p class="note">이 사이트는 매일 자동 수집되는 UPLEAT 데일리 트렌드 리포트(노션 데이터베이스)를 그대로 미러링하며, 새 리포트가 생성될 때마다 자동으로 업데이트됩니다. 총 {len(days)}일치 수록.</p>
</header>

<div class="tabs-row">
  <button class="tab-btn active" data-region="all">전체</button>
  <button class="tab-btn" data-region="해외">해외</button>
  <button class="tab-btn" data-region="국내">국내</button>
</div>

<div class="filter-row">
  <div class="search-box"><input id="searchInput" type="text" placeholder="날짜, 키워드, 기사 제목으로 검색"></div>
  <div class="pill-row">{"".join(pill_buttons)}</div>
</div>

<div class="content-layout">
  <div>
    <div class="card-grid" id="cardGrid">
{cards_html}
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
            + INDEX_SCRIPT
            + FOOT.format(scrolltop=SCROLLTOP_SCRIPT)
        )

    # ---- day pages ----
    for i, d in enumerate(days):
        date = d["intl"]["date"]
        label = d["intl"]["dateLabel"]
        gradient = GRADIENTS[i % len(GRADIENTS)]
        prev_day = days[i + 1]["intl"]["date"] if i + 1 < len(days) else None  # older
        next_day = days[i - 1]["intl"]["date"] if i - 1 >= 0 else None  # newer

        nav_prev = f'<a href="{prev_day}.html">← 전날</a>' if prev_day else '<span></span>'
        nav_next = f'<a href="{next_day}.html">다음날 →</a>' if next_day else '<span></span>'

        tags_html = "".join(f'<span class="tag-pill">#{esc(t)}</span>' for t in collect_tags(d))

        # related strip: up to 2 newer + 2 older neighbors, oldest-first
        window = [j for j in (i - 2, i - 1, i + 1, i + 2) if 0 <= j < len(days)]
        window.sort(reverse=True)
        related_tiles = []
        for j in window:
            rd = days[j]
            rdate = rd["intl"]["date"]
            rlabel = rd["intl"]["dateLabel"]
            day_num = rdate.split("-")[-1]
            weekday = rlabel.split(" ")[-1].replace("요일", "")
            related_tiles.append(f'''<a class="related-tile" href="{rdate}.html">
<div class="rt-art" style="background:{GRADIENTS[j % len(GRADIENTS)]}">{day_num}</div>
<div class="rt-label">{weekday}요일</div>
</a>''')
        related_html = ""
        if related_tiles:
            related_html = f'''<div class="related-strip">
<h3>다른 날짜 보기</h3>
<div class="related-scroll">{"".join(related_tiles)}</div>
</div>'''

        intl_panel = render_region_panel(d["intl"], "intl", active=True)
        domestic_panel = render_region_panel(d["domestic"], "domestic", active=False)

        body = f'''<div class="wrap" style="padding-bottom:0;">
<a class="back" href="../index.html">← 전체 목록</a>
</div>

<div class="hero-cover" style="background:{gradient}">
<div class="hero-inner">
<div class="hero-emoji">📡</div>
<div class="hero-info"><span class="hero-tag">UPLEAT Daily Brief</span><span class="hero-date">{label}</span></div>
</div>
</div>

<div class="wrap" style="padding-top:28px;">
<div class="detail-card">
<h1>{label} 트렌드 브리프</h1>
<div class="tabs-row region-tabs">
  <button class="tab-btn active" data-region="intl">🌐 해외</button>
  <button class="tab-btn" data-region="domestic">🇰🇷 국내</button>
</div>
{intl_panel}
{domestic_panel}
<div class="tag-cloud">{tags_html}</div>
<div class="detail-note">이 리포트는 UPLEAT가 매일 새벽 자동 수집한 해외·국내 AI/UX/디자인/테크 트렌드입니다. 올해 실제로 발행된 기사만 사용하며, 지어낸 URL이나 날짜는 포함하지 않습니다. 직전 7일과 중복된 기사는 "중복" 뱃지로 표시됩니다.</div>
</div>

<div class="daynav">{nav_prev}<span class="spacer"></span>{nav_next}</div>
{related_html}
<a class="back" href="../index.html">← 전체 목록</a>
{FOOTER_HTML}
</div>'''

        with open(os.path.join(DAYS_DIR, f"{date}.html"), "w", encoding="utf-8") as f:
            f.write(
                HEAD.format(title=f"{d['intl']['dateLabel']} · UPLEAT Daily Brief", style=STYLE, root_prefix="../")
                + body
                + DETAIL_SCRIPT
                + FOOT.format(scrolltop=SCROLLTOP_SCRIPT)
            )

    print(f"Built index.html + {len(days)} day pages: {', '.join(dates)}")


if __name__ == "__main__":
    build()
