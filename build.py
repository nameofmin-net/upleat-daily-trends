#!/usr/bin/env python3
"""Static site generator for the UPLEAT daily trend archive.

Reads data/YYYY-MM-DD.json files (each {"intl": {...}, "domestic": {...}})
and renders:
  - index.html: list of all days, newest first
  - days/YYYY-MM-DD.html: full day detail (해외 + 국내)

Usage: python3 build.py
"""
import json
import glob
import os
import html as htmllib

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
DAYS_DIR = os.path.join(ROOT, "days")

CATEGORY_ORDER = ["ai", "ux", "design", "biz"]

STYLE = """
:root{
  --accent:#2647E6;
  --accent-dim:#EEF1FD;
  --ink:#16181D;
  --sub:#6B7280;
  --line:#E6E8EC;
  --bg:#FAFAFB;
  --card:#FFFFFF;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{
  background:var(--bg);
  color:var(--ink);
  font-family:"IBM Plex Sans KR","Apple SD Gothic Neo",-apple-system,BlinkMacSystemFont,sans-serif;
  line-height:1.6;
}
.wrap{max-width:760px;margin:0 auto;padding:48px 20px 96px;}
a{color:var(--accent);text-decoration:none;}
a:hover{text-decoration:underline;}
header.site{margin-bottom:36px;}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);margin:0 0 8px;}
h1{font-size:26px;font-weight:800;margin:0 0 10px;letter-spacing:-.01em;}
.note{font-size:13px;color:var(--sub);background:var(--accent-dim);border-left:3px solid var(--accent);padding:12px 14px;border-radius:0 8px 8px 0;margin:18px 0 0;}
.back{display:inline-block;margin-bottom:20px;font-size:14px;font-weight:600;}
.day-list{list-style:none;margin:28px 0 0;padding:0;display:flex;flex-direction:column;gap:10px;}
.day-list li{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;transition:border-color .15s ease;}
.day-list li:hover{border-color:var(--accent);}
.day-list a{display:block;color:var(--ink);}
.day-list .date{font-weight:700;font-size:15px;}
.day-list .preview{font-size:13px;color:var(--sub);margin-top:4px;}
.day-list .preview b{color:var(--ink);font-weight:600;}
.daynav{display:flex;justify-content:space-between;align-items:center;margin:28px 0;font-size:14px;font-weight:600;}
.daynav .spacer{flex:1;}
.region-block{margin-bottom:40px;}
.region-head{display:flex;align-items:center;gap:8px;margin-bottom:6px;}
.region-badge{font-size:11px;font-weight:800;letter-spacing:.03em;padding:3px 10px;border-radius:999px;background:var(--accent-dim);color:var(--accent);}
.region-date{font-size:20px;font-weight:800;}
.takeaway{margin:14px 0 20px;padding:14px 16px;background:var(--accent-dim);border-radius:10px;font-size:14px;font-weight:600;}
.takeaway b{color:var(--accent);}
details.cat{border:1px solid var(--line);border-radius:10px;margin-bottom:10px;background:var(--card);overflow:hidden;}
details.cat summary{cursor:pointer;list-style:none;padding:12px 16px;font-size:13px;font-weight:700;letter-spacing:.02em;display:flex;align-items:center;gap:8px;}
details.cat summary::-webkit-details-marker{display:none;}
details.cat summary::before{content:"▸";color:var(--accent);transition:transform .15s ease;}
details.cat[open] summary::before{transform:rotate(90deg);}
.cat-label{color:var(--accent);}
.cat-count{color:var(--sub);font-weight:500;}
.cat-body{padding:4px 16px 14px;}
.empty-note{font-size:13px;color:var(--sub);padding:6px 0 10px;}
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

HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{style}</style>
</head>
<body>
<div class="wrap">
"""

FOOT = """
<footer class="site">UPLEAT &middot; Daily Trend Archive</footer>
</div>
</body>
</html>
"""


def esc(s):
    return htmllib.escape(s, quote=False) if s else ""


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


def render_region(day):
    region_label = "🌐 해외" if day["region"] == "해외" else "🇰🇷 국내"
    cats_html = []
    for cat in day["categories"]:
        n = len(cat["items"])
        cats_html.append(f'''<details class="cat">
<summary><span class="cat-label">{cat['label']}</span><span class="cat-count">({n})</span></summary>
<div class="cat-body">{render_items(cat['items'])}</div>
</details>''')
    return f'''<section class="region-block">
<div class="region-head"><span class="region-badge">{region_label}</span><span class="region-date">{day['dateLabel']}</span></div>
<div class="takeaway">{day['takeawayHtml']}</div>
{"".join(cats_html)}
</section>'''


def takeaway_preview(day):
    text = day["takeawayHtml"].replace("<b>", "").replace("</b>", "")
    if len(text) > 70:
        text = text[:70] + "…"
    return esc(text)


def build():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    days = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            days.append(json.load(f))
    days.sort(key=lambda d: d["intl"]["date"], reverse=True)
    dates = [d["intl"]["date"] for d in days]

    os.makedirs(DAYS_DIR, exist_ok=True)

    # index.html
    list_items = []
    for d in days:
        date = d["intl"]["date"]
        label = d["intl"]["dateLabel"]
        preview = takeaway_preview(d["intl"])
        list_items.append(f'''<li><a href="days/{date}.html">
<div class="date">{label}</div>
<div class="preview"><b>해외</b> {preview}</div>
</a></li>''')

    index_body = f'''<header class="site">
<p class="eyebrow">UPLEAT</p>
<h1>UPLEAT 데일리 트렌드 아카이브</h1>
<p class="note">이 사이트는 매일 자동 수집되는 UPLEAT 데일리 트렌드 리포트(노션 데이터베이스)를 그대로 미러링하며, 새 리포트가 생성될 때마다 자동으로 업데이트됩니다.</p>
</header>
<ul class="day-list">
{"".join(list_items)}
</ul>'''

    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(HEAD.format(title="UPLEAT 데일리 트렌드 아카이브", style=STYLE) + index_body + FOOT)

    # day pages
    for i, d in enumerate(days):
        date = d["intl"]["date"]
        prev_day = days[i + 1]["intl"]["date"] if i + 1 < len(days) else None  # older
        next_day = days[i - 1]["intl"]["date"] if i - 1 >= 0 else None  # newer

        nav_prev = f'<a href="{prev_day}.html">← 전날</a>' if prev_day else '<span></span>'
        nav_next = f'<a href="{next_day}.html">다음날 →</a>' if next_day else '<span></span>'

        body = f'''<a class="back" href="../index.html">← 전체 목록</a>
<header class="site">
<p class="eyebrow">UPLEAT Daily Brief</p>
<h1>{d['intl']['dateLabel']}</h1>
</header>
{render_region(d['intl'])}
{render_region(d['domestic'])}
<div class="daynav">{nav_prev}<span class="spacer"></span>{nav_next}</div>
<a class="back" href="../index.html">← 전체 목록</a>'''

        with open(os.path.join(DAYS_DIR, f"{date}.html"), "w", encoding="utf-8") as f:
            f.write(HEAD.format(title=f"{d['intl']['dateLabel']} · UPLEAT Daily Brief", style=STYLE) + body + FOOT)

    print(f"Built index.html + {len(days)} day pages: {', '.join(dates)}")


if __name__ == "__main__":
    build()
