#!/usr/bin/env python3
"""Static site generator for the UPLEAT daily trend archive.

Reads data/YYYY-MM-DD.json files (each {"intl": {...}, "domestic": {...}},
day-grouped with categories of articles) and flattens them into a single
reverse-chronological feed on index.html (search, category pills, load-more).
There is no separate per-article detail page — each list row shows the full
insight inline, a link to the original source, and comments open in a
floating right-side panel (Notion-style) instead of navigating away.

Articles whose source JSON marks them `duplicate: true` (same URL already
published within the rolling 7-day dedup window) are skipped entirely.

Each article looks for a generated thumbnail at assets/thumbs/{id}.{ext}
(jpg/jpeg/png/webp). If present it's used as the row's thumbnail; otherwise a
flat category-tinted placeholder is shown instead.

Usage: python3 build.py
"""
import json
import glob
import os
import re
import shutil
import html as htmllib

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
ARTICLES_DIR = os.path.join(ROOT, "articles")
ASSETS_DIR = os.path.join(ROOT, "assets", "thumbs")
THUMB_EXTS = (".jpg", ".jpeg", ".png", ".webp")
COMMENTS_WORKER_URL = "https://upleat-trend-comments.dkdldb3144.workers.dev"

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

STYLE = """
:root{
  --accent:#1868E0;
  --accent-dim:#EAF2FE;
  --ink:#111214;
  --sub:#525252;
  --sub2:#8B8B8B;
  --line:#E5E5E5;
  --bg:#FFFFFF;
  --card:#FFFFFF;
  --shadow:0 4px 10px rgba(16,24,40,.07), 0 1px 2px rgba(16,24,40,.04);
}
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
html,body{margin:0;padding:0;}
body{
  background:var(--bg);
  color:var(--ink);
  font-family:"IBM Plex Sans KR","Apple SD Gothic Neo",-apple-system,BlinkMacSystemFont,sans-serif;
  line-height:1.6;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1440px;margin:0 auto;padding:36px 20px 80px;}
a{color:inherit;text-decoration:none;}
.gnb-sticky{position:sticky;top:0;z-index:40;background:#fff;margin-bottom:28px;}
.topbar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;padding:16px 0;border-bottom:2px solid var(--ink);}
.brand{font-weight:700;letter-spacing:.02em;font-size:15px;color:var(--ink);flex:0 0 auto;}
.brand a{color:inherit;}
.gnb-right{display:flex;align-items:center;gap:20px;flex-wrap:wrap;flex:1;justify-content:flex-end;}

header.site{margin-bottom:22px;}
.header-row{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;}
.region-tab-row{display:flex;gap:20px;flex:0 0 auto;}
.region-tab-btn{appearance:none;cursor:pointer;font-family:inherit;border:none;background:none;color:var(--sub);font-size:14px;font-weight:600;padding:4px 0;transition:color .12s ease;}
.region-tab-btn.active{color:var(--ink);font-weight:700;}
.region-tab-btn:hover:not(.active){color:var(--ink);}
h1{font-size:28px;font-weight:700;margin:0 0 10px;letter-spacing:-.01em;}
.note{font-size:13px;color:var(--sub);background:#F7F7F7;padding:14px 16px;margin:16px 0 0;line-height:1.7;}

/* GNB search + text-only tabs — right side of the single-row GNB, no chrome */
.search-box{position:relative;max-width:220px;flex:1;min-width:150px;margin:0;}
.search-box input{width:100%;padding:6px 6px 6px 22px;border:none;background:none;font-family:inherit;font-size:13.5px;color:var(--ink);}
.search-box input:focus{outline:none;}
.search-box input::placeholder{color:var(--sub2);}
.search-icon{position:absolute;left:0;top:50%;transform:translateY(-50%);color:var(--sub2);pointer-events:none;}
.pill-row{display:flex;gap:18px;flex-wrap:wrap;flex:0 0 auto;}
.pill-btn{display:inline-block;appearance:none;cursor:pointer;font-family:inherit;border:none;background:none;color:var(--sub);font-size:13px;font-weight:600;padding:7px 0;transition:color .12s ease;}
.pill-btn.active{color:var(--ink);font-weight:700;}
.pill-btn:hover:not(.active){color:var(--ink);}

/* article feed — left-thumbnail / right-content list rows, full insight inline */
.feed-list{display:flex;flex-direction:column;}
.feed-item{border-bottom:1px solid var(--line);transition:opacity .4s ease, transform .4s ease;}
.feed-item:first-child{border-top:none;}
.feed-row{display:flex;gap:24px;padding:24px 0;align-items:flex-start;}
.feed-thumb{flex:0 0 200px;width:200px;aspect-ratio:16/10;background:#F2F2F2;overflow:hidden;position:relative;display:flex;align-items:center;justify-content:center;}
@media (max-width:640px){.feed-row{flex-direction:column;gap:14px;}.feed-thumb{flex:0 0 auto;width:100%;aspect-ratio:16/9;}}
.feed-thumb img{width:100%;height:100%;object-fit:cover;display:block;}
.feed-thumb-emoji{font-size:28px;opacity:.5;}
.feed-content{flex:1;min-width:0;display:flex;flex-direction:column;}
.feed-top-row{display:flex;align-items:center;gap:10px;margin-bottom:9px;}
.feed-eyebrow{display:inline-flex;align-items:center;gap:4px;background:var(--ink);color:#fff;font-size:10.5px;font-weight:700;letter-spacing:.04em;padding:4px 9px;border-radius:4px;}
.feed-hashtag{font-size:12px;font-weight:700;color:var(--accent);}
.feed-title-row{display:flex;align-items:center;gap:7px;margin:0 0 6px;}
.badge-new{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:3px;background:#E0352B;color:#fff;font-size:10px;font-weight:800;line-height:1;}
.feed-title{font-size:20px;font-weight:700;line-height:1.4;letter-spacing:-.008em;color:var(--ink);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.feed-item:hover .feed-title{color:var(--accent);}
.feed-summary{font-size:16px;color:var(--sub);line-height:1.7;margin:0 0 10px;}
.feed-summary b{color:var(--accent);}
.feed-meta{display:flex;align-items:center;gap:7px;margin-top:auto;flex-wrap:wrap;}
.feed-src-name{font-size:11px;font-weight:600;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.feed-dot{font-size:11px;color:var(--sub2);flex:0 0 auto;}
.feed-date{font-size:11px;color:var(--sub2);flex:0 0 auto;}
.comment-fab{display:inline-flex;align-self:flex-start;align-items:center;gap:5px;cursor:pointer;font-family:inherit;background:#fff;border:1px solid var(--line);border-radius:999px;padding:7px 13px;font-size:12px;font-weight:600;color:var(--sub);margin-bottom:10px;}
.comment-fab:hover{border-color:var(--accent);color:var(--accent);}
.comment-fab svg{width:14px;height:14px;flex:0 0 auto;}
.hidden-initial{display:none;}

.loadmore-wrap{text-align:center;margin-top:36px;}
.loadmore-btn{appearance:none;cursor:pointer;font-family:inherit;background:var(--card);border:1px solid var(--line);color:var(--sub);font-weight:700;font-size:14px;padding:13px 0;width:100%;border-radius:10px;box-shadow:var(--shadow);}
.loadmore-btn:hover{border-color:var(--accent);color:var(--accent);}
.no-results{font-size:14px;color:var(--sub);padding:40px 0;text-align:center;}

/* "최근 핵심 인사이트" — full-width strip below the grid, same 4-col system as the feed */
.rail-strip{margin-top:52px;padding-top:28px;border-top:1px solid var(--line);}
.rail-strip h3{font-size:14px;margin:0 0 18px;font-weight:700;}
.rail-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:32px;}
@media (max-width:860px){.rail-grid{grid-template-columns:repeat(2,1fr);gap:24px;}}
@media (max-width:560px){.rail-grid{grid-template-columns:1fr;gap:24px;}}
.rail-item{padding:0;}
.rail-text{font-size:12.5px;color:var(--ink);line-height:1.5;cursor:pointer;}
.rail-text b{color:var(--accent);}
.rail-date{display:block;font-size:11px;color:var(--sub2);margin-top:4px;}

.scrolltop{position:fixed;right:24px;bottom:24px;width:44px;height:44px;border-radius:50%;background:var(--ink);color:#fff;border:none;cursor:pointer;font-size:16px;box-shadow:0 6px 16px rgba(0,0,0,.2);opacity:0;pointer-events:none;transition:opacity .2s ease, transform .2s ease;z-index:50;}
.scrolltop.show{opacity:1;pointer-events:auto;}
.scrolltop:hover{transform:translateY(-2px);}

/* floating comment panel (Notion-style) */
.comment-panel-overlay{position:fixed;inset:0;background:transparent;z-index:99;display:none;}
.comment-panel-overlay.open{display:block;}
.comment-panel{position:fixed;top:90px;right:24px;width:400px;max-width:calc(100vw - 32px);max-height:calc(100vh - 114px);background:#fff;border-radius:16px;box-shadow:0 20px 48px rgba(16,24,40,.18), 0 2px 10px rgba(16,24,40,.08);z-index:100;opacity:0;transform:translateY(-10px) scale(.98);pointer-events:none;transition:opacity .18s ease, transform .18s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;overflow:hidden;}
.comment-panel.open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto;}
@media (max-width:640px){.comment-panel{top:auto;bottom:0;right:0;left:0;width:100%;max-width:100%;max-height:80vh;border-radius:16px 16px 0 0;transform:translateY(16px);}
.comment-panel.open{transform:translateY(0);}}
.comment-panel-header{display:flex;align-items:flex-start;gap:12px;padding:18px 18px 14px;border-bottom:1px solid var(--line);}
.comment-panel-title{flex:1;font-size:14px;font-weight:700;line-height:1.5;margin:0;}
.comment-panel-close{flex:0 0 auto;appearance:none;cursor:pointer;background:none;border:none;font-size:22px;color:var(--sub2);line-height:1;padding:0;}
.comment-panel-close:hover{color:var(--ink);}
.comment-panel-body{flex:1;min-height:0;overflow-y:auto;padding:18px;}

/* comments (reused inside the floating panel) */
.comments-count{color:var(--sub2);font-weight:600;}
.comment-identity{font-size:12.5px;color:var(--sub2);margin-bottom:12px;}
.comment-identity strong{color:var(--accent);}
.comment-form{margin-bottom:24px;}
.comment-textarea{width:100%;min-height:76px;padding:12px 14px;border:1px solid var(--line);border-radius:8px;font-family:inherit;font-size:14px;color:var(--ink);resize:vertical;}
.comment-textarea:focus{outline:none;border-color:var(--accent);}
.comment-submit-btn{appearance:none;cursor:pointer;font-family:inherit;margin-top:10px;background:var(--ink);color:#fff;border:none;font-weight:700;font-size:13.5px;padding:10px 20px;border-radius:8px;}
.comment-submit-btn:hover{background:var(--accent);}
.comment-submit-btn:disabled{opacity:.5;cursor:default;}
.comment-list{display:flex;flex-direction:column;gap:16px;}
.comment-item{padding-bottom:16px;border-bottom:1px solid var(--line);}
.comment-item:last-child{border-bottom:none;padding-bottom:0;}
.comment-head{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;}
.comment-name{font-size:13px;font-weight:700;color:var(--ink);}
.comment-date{font-size:11.5px;color:var(--sub2);}
.comment-body{font-size:14px;color:#2E3238;line-height:1.7;white-space:pre-wrap;word-break:break-word;}
.comment-empty{font-size:13px;color:var(--sub2);padding:12px 0;}

/* Nexty AI 트렌드 Q&A floating button + panel */
.ai-ask-wrap{position:fixed;right:20px;bottom:80px;z-index:50;display:flex;flex-direction:column;align-items:flex-end;gap:8px;}
@media (max-width:640px){.ai-ask-wrap{bottom:76px;right:20px;}}
.ai-ask-fab{position:static;display:inline-flex;align-items:center;gap:8px;appearance:none;cursor:pointer;font-family:inherit;background:var(--accent);color:#fff;border:none;border-radius:999px;padding:8px 18px 8px 8px;font-size:13.5px;font-weight:700;box-shadow:0 6px 16px rgba(0,0,0,.22);transition:transform .2s ease;}
.ai-ask-fab:hover{transform:translateY(-2px);}
.nexty-avatar{width:36px;height:36px;flex:0 0 auto;display:block;animation-name:nexty-float, nexty-wiggle;animation-duration:2.4s, 6s;animation-timing-function:ease-in-out, ease-in-out;animation-iteration-count:infinite, infinite;}
@keyframes nexty-float{0%,100%{translate:0 0;}50%{translate:0 -4px;}}
@keyframes nexty-wiggle{0%,83%,100%{rotate:0deg;}86%{rotate:-10deg;}89%{rotate:9deg;}92%{rotate:-7deg;}95%{rotate:4deg;}98%{rotate:0deg;}}
.nexty-callout{background:#fff;color:var(--ink);font-size:12px;font-weight:700;padding:8px 13px;border-radius:10px;box-shadow:0 6px 16px rgba(0,0,0,.16);position:relative;opacity:0;translate:0 6px;pointer-events:none;animation:nexty-callout-pop 8s ease-in-out infinite;}
.nexty-callout::after{content:'';position:absolute;right:22px;bottom:-5px;width:10px;height:10px;background:#fff;rotate:45deg;}
@keyframes nexty-callout-pop{0%,55%{opacity:0;translate:0 6px;}62%,80%{opacity:1;translate:0 0;}88%,100%{opacity:0;translate:0 6px;}}
.ai-ask-wrap.panel-open{display:none;}
@media (prefers-reduced-motion: reduce){.nexty-avatar{animation:none;}.nexty-callout{animation:none;opacity:0;}}
.ai-panel-overlay{position:fixed;inset:0;background:transparent;z-index:99;display:none;}
.ai-panel-overlay.open{display:block;}
.ai-panel{position:fixed;right:20px;bottom:144px;top:auto;width:400px;max-width:calc(100vw - 32px);max-height:calc(100vh - 170px);background:#fff;border-radius:16px;box-shadow:0 20px 48px rgba(16,24,40,.18), 0 2px 10px rgba(16,24,40,.08);z-index:100;opacity:0;transform:translateY(10px) scale(.98);transform-origin:bottom right;pointer-events:none;transition:opacity .18s ease, transform .18s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;overflow:hidden;}
.ai-panel.open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto;}
@media (max-width:640px){.ai-panel{top:auto;bottom:0;right:0;left:0;width:100%;max-width:100%;max-height:80vh;border-radius:16px 16px 0 0;transform:translateY(16px);}
.ai-panel.open{transform:translateY(0);}}
.ai-panel-header{display:flex;align-items:flex-start;gap:12px;padding:18px 18px 14px;border-bottom:1px solid var(--line);}
.ai-panel-avatar{width:28px;height:28px;flex:0 0 auto;display:block;margin-top:2px;}
.ai-panel-title{flex:1;font-size:14px;font-weight:700;line-height:1.5;margin:0;}
.ai-panel-sub{font-size:11.5px;color:var(--sub2);margin:2px 0 0;}
.ai-panel-close{flex:0 0 auto;appearance:none;cursor:pointer;background:none;border:none;font-size:22px;color:var(--sub2);line-height:1;padding:0;}
.ai-panel-close:hover{color:var(--ink);}
.ai-panel-body{flex:1;min-height:0;overflow-y:auto;padding:18px;display:flex;flex-direction:column;gap:14px;}
.ai-msg{font-size:14px;line-height:1.7;white-space:pre-wrap;word-break:break-word;}
.ai-msg-user{align-self:flex-end;max-width:85%;background:var(--ink);color:#fff;border-radius:12px 12px 2px 12px;padding:9px 13px;}
.ai-msg-bot{align-self:flex-start;max-width:92%;background:#F2F2F2;color:var(--ink);border-radius:12px 12px 12px 2px;padding:9px 13px;}
.ai-msg-bot.loading{color:var(--sub2);font-style:italic;}
.ai-panel-form{display:flex;gap:8px;padding:14px 18px;border-top:1px solid var(--line);flex:0 0 auto;}
.ai-panel-input{flex:1;min-width:0;padding:10px 13px;border:1px solid var(--line);border-radius:8px;font-family:inherit;font-size:14px;color:var(--ink);}
.ai-panel-input:focus{outline:none;border-color:var(--accent);}
.ai-panel-send{flex:0 0 auto;appearance:none;cursor:pointer;font-family:inherit;background:var(--ink);color:#fff;border:none;font-weight:700;font-size:13.5px;padding:10px 16px;border-radius:8px;}
.ai-panel-send:hover{background:var(--accent);}
.ai-panel-send:disabled{opacity:.5;cursor:default;}
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
  var searchForm = searchInput ? searchInput.closest('form') : null;
  var pillBtns = Array.prototype.slice.call(document.querySelectorAll('.pill-btn'));
  var regionBtns = Array.prototype.slice.call(document.querySelectorAll('.region-tab-btn'));

  var params = new URLSearchParams(location.search);
  var state = { cat: params.get('cat') || 'all', region: params.get('region') || 'all', q: (params.get('q') || '').trim().toLowerCase(), visible: PAGE_SIZE };
  if (searchInput && params.get('q')) searchInput.value = params.get('q');
  pillBtns.forEach(function(b){ b.classList.toggle('active', b.dataset.cat === state.cat); });
  regionBtns.forEach(function(b){ b.classList.toggle('active', b.dataset.region === state.region); });

  function matches(item){
    if (state.cat !== 'all' && item.dataset.cat !== state.cat) return false;
    if (state.region !== 'all' && item.dataset.region !== state.region) return false;
    if (state.q && item.dataset.search.indexOf(state.q) === -1) return false;
    return true;
  }

  function render(){
    var shown = 0, matched = 0;
    items.forEach(function(item){
      var ok = matches(item);
      if (ok) matched++;
      var within = ok && shown < state.visible;
      var wasHidden = item.style.display === 'none' || item.classList.contains('hidden-initial');
      item.style.display = ok ? '' : 'none';
      item.classList.toggle('hidden-initial', ok && !within);
      if (within) {
        shown++;
        if (wasHidden) {
          item.style.opacity = '0';
          item.style.transform = 'translateY(28px)';
          requestAnimationFrame(function(){
            requestAnimationFrame(function(){
              item.style.opacity = '1';
              item.style.transform = 'translateY(0)';
            });
          });
        }
      }
    });
    var hasMore = matched > state.visible;
    loadBtn.style.display = hasMore ? '' : 'none';
    noResults.style.display = (matched === 0) ? '' : 'none';
    return hasMore;
  }

  function loadMore(){
    state.visible += PAGE_SIZE;
    render();
  }

  if (searchForm) searchForm.addEventListener('submit', function(e){ e.preventDefault(); });
  searchInput.addEventListener('input', function(){
    state.q = this.value.trim().toLowerCase();
    state.visible = PAGE_SIZE;
    render();
  });
  pillBtns.forEach(function(btn){
    btn.addEventListener('click', function(e){
      e.preventDefault();
      pillBtns.forEach(function(b){ b.classList.remove('active'); });
      btn.classList.add('active');
      state.cat = btn.dataset.cat;
      state.visible = PAGE_SIZE;
      render();
    });
  });
  regionBtns.forEach(function(btn){
    btn.addEventListener('click', function(){
      regionBtns.forEach(function(b){ b.classList.remove('active'); });
      btn.classList.add('active');
      state.region = btn.dataset.region;
      state.visible = PAGE_SIZE;
      render();
    });
  });
  loadBtn.addEventListener('click', loadMore);

  render();

  // auto-expand as the user scrolls near the load-more button, no click needed
  var sentinel = document.getElementById('loadMoreWrap') || loadBtn;
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (entry.isIntersecting && loadBtn.style.display !== 'none') loadMore();
      });
    }, { rootMargin: '600px 0px' });
    io.observe(sentinel);
  }
  // backup check on scroll in case IntersectionObserver misses a fast/jump scroll
  var scrollCheckQueued = false;
  window.addEventListener('scroll', function(){
    if (scrollCheckQueued || loadBtn.style.display === 'none') return;
    scrollCheckQueued = true;
    requestAnimationFrame(function(){
      scrollCheckQueued = false;
      if (loadBtn.style.display === 'none') return;
      var r = sentinel.getBoundingClientRect();
      if (r.top < window.innerHeight + 600) loadMore();
    });
  }, { passive: true });
})();
</script>
"""

COMMENT_PANEL_SCRIPT = """
<div class="comment-panel-overlay" id="commentPanelOverlay"></div>
<aside class="comment-panel" id="commentPanel">
  <div class="comment-panel-header">
    <h3 class="comment-panel-title" id="commentPanelTitle"></h3>
    <button class="comment-panel-close" id="commentPanelClose" aria-label="닫기">&times;</button>
  </div>
  <div class="comment-panel-body">
    <p class="comment-identity">지금 <strong class="anon-name" id="panelAnonName">익명</strong>으로 댓글을 남길 수 있어요.</p>
    <form class="comment-form" id="commentPanelForm">
      <textarea class="comment-textarea" id="commentPanelTextarea" placeholder="의견을 남겨주세요" maxlength="2000" required></textarea>
      <button type="submit" class="comment-submit-btn">댓글 등록</button>
    </form>
    <div class="comment-list" id="commentPanelList"></div>
    <p class="comment-empty" id="commentPanelEmpty" style="display:none">아직 댓글이 없어요. 첫 댓글을 남겨보세요.</p>
  </div>
</aside>
<script>
(function(){
  var WORKER_URL = "%s";
  var ANIMALS = ["여우","너구리","고양이","강아지","수달","판다","펭귄","부엉이","다람쥐","햄스터","토끼","고슴도치","코알라","캥거루","라마","알파카","플라밍고","두더지","미어캣","오소리","비버","사막여우","북극곰","바다표범","돌고래","수리부엉이","삵","담비","산양","꽃사슴"];

  function getAnonName(){
    try {
      var saved = localStorage.getItem('upleat_anon_name');
      if (saved) return saved;
    } catch(e){}
    var name = '익명의 ' + ANIMALS[Math.floor(Math.random() * ANIMALS.length)];
    try { localStorage.setItem('upleat_anon_name', name); } catch(e){}
    return name;
  }

  function escapeHtml(s){
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function pad2(n){ return (n < 10 ? '0' : '') + n; }

  function formatDate(iso){
    try {
      var d = new Date(iso);
      return d.getFullYear() + '.' + pad2(d.getMonth()+1) + '.' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
    } catch(e){ return ''; }
  }

  function kstDateStr(d){
    var kst = new Date(d.getTime() + (9 * 60 - d.getTimezoneOffset()) * 60000);
    return kst.getFullYear() + '-' + pad2(kst.getMonth()+1) + '-' + pad2(kst.getDate());
  }

  function isToday(iso){
    try { return kstDateStr(new Date(iso)) === kstDateStr(new Date()); } catch(e){ return false; }
  }

  var anonName = getAnonName();
  document.getElementById('panelAnonName').textContent = anonName;

  var overlay = document.getElementById('commentPanelOverlay');
  var panel = document.getElementById('commentPanel');
  var titleEl = document.getElementById('commentPanelTitle');
  var listEl = document.getElementById('commentPanelList');
  var emptyEl = document.getElementById('commentPanelEmpty');
  var form = document.getElementById('commentPanelForm');
  var textarea = document.getElementById('commentPanelTextarea');
  var submitBtn = form.querySelector('.comment-submit-btn');
  var currentPageId = null;

  function updateCountBadge(pageId, n, hasToday){
    var item = document.querySelector('.feed-item[data-id="' + pageId + '"]');
    if (!item) return;
    var btn = item.querySelector('.comment-fab');
    if (!btn) return;
    btn.querySelector('.cc-num').textContent = n > 0 ? n : '';
    var badge = btn.querySelector('.comment-fab-new');
    if (badge) badge.style.display = hasToday ? 'inline-flex' : 'none';
  }

  function renderList(comments){
    if (!comments.length){
      listEl.innerHTML = '';
      emptyEl.style.display = '';
      return;
    }
    emptyEl.style.display = 'none';
    listEl.innerHTML = comments.map(function(c){
      var newBadge = isToday(c.created_at) ? '<span class="badge-new">N</span>' : '';
      return '<div class="comment-item"><div class="comment-head"><span class="comment-name">' + escapeHtml(c.name) + '</span>' + newBadge + '<span class="comment-date">' + formatDate(c.created_at) + '</span></div><div class="comment-body">' + escapeHtml(c.body) + '</div></div>';
    }).join('');
  }

  function loadComments(pageId){
    fetch(WORKER_URL + '/api/comments?page=' + encodeURIComponent(pageId))
      .then(function(r){ return r.json(); })
      .then(function(data){
        var comments = data.comments || [];
        if (pageId === currentPageId) renderList(comments);
        updateCountBadge(pageId, comments.length, comments.some(function(c){ return isToday(c.created_at); }));
      })
      .catch(function(){ /* fail quietly */ });
  }

  function openPanel(pageId, title){
    currentPageId = pageId;
    titleEl.textContent = title || '';
    listEl.innerHTML = '';
    emptyEl.style.display = 'none';
    textarea.value = '';
    panel.classList.add('open');
    overlay.classList.add('open');
    loadComments(pageId);
  }

  function closePanel(){
    panel.classList.remove('open');
    overlay.classList.remove('open');
    currentPageId = null;
  }

  document.querySelectorAll('.comment-fab').forEach(function(btn){
    btn.addEventListener('click', function(e){
      e.preventDefault();
      e.stopPropagation();
      openPanel(btn.dataset.id, btn.dataset.title);
    });
    btn.addEventListener('keydown', function(e){
      if (e.key === 'Enter' || e.key === ' '){
        e.preventDefault();
        e.stopPropagation();
        openPanel(btn.dataset.id, btn.dataset.title);
      }
    });
  });
  document.querySelectorAll('.rail-text[data-id]').forEach(function(el){
    el.addEventListener('click', function(e){
      e.preventDefault();
      openPanel(el.dataset.id, el.dataset.title);
    });
  });

  document.getElementById('commentPanelClose').addEventListener('click', closePanel);
  overlay.addEventListener('click', closePanel);
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && panel.classList.contains('open')) closePanel();
  });

  form.addEventListener('submit', function(e){
    e.preventDefault();
    var body = textarea.value.trim();
    if (!body || !currentPageId) return;
    var pageId = currentPageId;
    submitBtn.disabled = true;
    fetch(WORKER_URL + '/api/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page: pageId, name: anonName, body: body })
    }).then(function(r){ return r.json(); })
      .then(function(res){
        if (res.ok){
          textarea.value = '';
          loadComments(pageId);
        }
      })
      .catch(function(){})
      .finally(function(){ submitBtn.disabled = false; });
  });

  // initial comment-count badges for every row in the feed
  fetch(WORKER_URL + '/api/comments/counts')
    .then(function(r){ return r.json(); })
    .then(function(data){
      var counts = data.counts || {};
      Object.keys(counts).forEach(function(pageId){
        var c = counts[pageId];
        updateCountBadge(pageId, c.n, isToday(c.latest));
      });
    })
    .catch(function(){ /* fail quietly */ });
})();
</script>
""" % COMMENTS_WORKER_URL

AI_ASK_SCRIPT = """
<div class="ai-ask-wrap" id="aiAskWrap">
  <span class="nexty-callout">저한테 물어보세요!</span>
  <button class="ai-ask-fab" id="aiAskFab">
    <img class="nexty-avatar" src="assets/brand/nexty.png" alt="Nexty" width="36" height="36">
    Nexty에게 묻기
  </button>
</div>
<div class="ai-panel-overlay" id="aiPanelOverlay"></div>
<aside class="ai-panel" id="aiPanel">
  <div class="ai-panel-header">
    <img class="ai-panel-avatar" src="assets/brand/nexty.png" alt="Nexty" width="28" height="28">
    <div style="flex:1">
      <h3 class="ai-panel-title">Nexty</h3>
      <p class="ai-panel-sub">최근 며칠간의 트렌드 기사를 바탕으로 답해요</p>
    </div>
    <button class="ai-panel-close" id="aiPanelClose" aria-label="닫기">&times;</button>
  </div>
  <div class="ai-panel-body" id="aiPanelBody">
    <div class="ai-msg ai-msg-bot">안녕하세요, 저는 Nexty예요! 최근 UPLEAT 트렌드 기사에 대해 궁금한 걸 물어보세요. (예: "오늘 AI 쪽 트렌드 뭐가 있었어?")</div>
  </div>
  <form class="ai-panel-form" id="aiPanelForm">
    <input class="ai-panel-input" id="aiPanelInput" type="text" placeholder="질문을 입력하세요" maxlength="300" required autocomplete="off">
    <button type="submit" class="ai-panel-send">전송</button>
  </form>
</aside>
<script>
(function(){
  var WORKER_URL = "%s";
  var wrap = document.getElementById('aiAskWrap');
  var fab = document.getElementById('aiAskFab');
  var overlay = document.getElementById('aiPanelOverlay');
  var panel = document.getElementById('aiPanel');
  var body = document.getElementById('aiPanelBody');
  var form = document.getElementById('aiPanelForm');
  var input = document.getElementById('aiPanelInput');
  var sendBtn = form.querySelector('.ai-panel-send');

  function escapeHtml(s){
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function addMsg(text, who){
    var div = document.createElement('div');
    div.className = 'ai-msg ai-msg-' + who;
    div.innerHTML = escapeHtml(text).replace(/\\n/g, '<br>');
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    return div;
  }

  function typeIntoElement(el, text){
    el.textContent = '';
    var i = 0;
    var CHARS_PER_TICK = 2;
    var TICK_MS = 16;
    function tick(){
      var n = 0;
      while (i < text.length && n < CHARS_PER_TICK) {
        var ch = text.charAt(i);
        if (ch === '\\n') {
          el.appendChild(document.createElement('br'));
        } else {
          el.appendChild(document.createTextNode(ch));
        }
        i++; n++;
      }
      body.scrollTop = body.scrollHeight;
      if (i < text.length) setTimeout(tick, TICK_MS);
    }
    tick();
  }

  function openPanel(){
    panel.classList.add('open');
    overlay.classList.add('open');
    wrap.classList.add('panel-open');
    setTimeout(function(){ input.focus(); }, 50);
  }

  function closePanel(){
    panel.classList.remove('open');
    overlay.classList.remove('open');
    wrap.classList.remove('panel-open');
  }

  fab.addEventListener('click', openPanel);
  document.getElementById('aiPanelClose').addEventListener('click', closePanel);
  overlay.addEventListener('click', closePanel);
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && panel.classList.contains('open')) closePanel();
  });

  form.addEventListener('submit', function(e){
    e.preventDefault();
    var q = input.value.trim();
    if (!q) return;
    addMsg(q, 'user');
    input.value = '';
    sendBtn.disabled = true;
    var loadingEl = addMsg('생각 중...', 'bot');
    loadingEl.classList.add('loading');
    fetch(WORKER_URL + '/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    }).then(function(r){ return r.json().then(function(data){ return { ok: r.ok, data: data }; }); })
      .then(function(res){
        loadingEl.classList.remove('loading');
        var answer = res.ok && res.data.answer ? res.data.answer.trim() : '';
        if (answer) {
          typeIntoElement(loadingEl, answer);
        } else if (res.data && res.data.error === 'daily limit reached') {
          loadingEl.textContent = '오늘 질문 가능 횟수를 모두 사용했어요. 내일 다시 시도해주세요.';
        } else {
          loadingEl.textContent = '답변을 가져오지 못했어요. 잠시 후 다시 시도해주세요.';
        }
        body.scrollTop = body.scrollHeight;
      })
      .catch(function(){
        loadingEl.classList.remove('loading');
        loadingEl.textContent = '네트워크 오류로 답변을 가져오지 못했어요.';
      })
      .finally(function(){ sendBtn.disabled = false; });
  });
})();
</script>
""" % COMMENTS_WORKER_URL

HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{style}</style>
</head>
<body>
<div class="gnb-sticky">
<div class="topbar wrap" style="padding-top:0;padding-bottom:0;">
  <div class="brand"><a href="index.html">UPLEAT · Daily Trend Archive</a></div>
  <div class="gnb-right">
    <form class="search-box" action="index.html" method="get">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
      <input id="searchInput" name="q" type="text" placeholder="날짜, 키워드, 기사 제목으로 검색">
    </form>
    <div class="pill-row">{gnb_pills}</div>
  </div>
</div>
</div>
"""

FOOT = """
{scrolltop}
</body>
</html>
"""


def esc(s):
    return htmllib.escape(s, quote=False) if s else ""


def esc_attr(s):
    return htmllib.escape(s, quote=True) if s else ""


def strip_tags(s):
    return re.sub(r"</?b>", "", s or "")


def first_paragraph(text_html):
    """The insight's first <br><br>-separated paragraph, <b> emphasis kept intact."""
    return re.split(r"<br\s*/?>\s*<br\s*/?>", text_html or "", maxsplit=1)[0]


def find_thumb(article_id):
    """Return the root-relative path to a generated thumbnail, or None."""
    for ext in THUMB_EXTS:
        if os.path.exists(os.path.join(ASSETS_DIR, article_id + ext)):
            return f"assets/thumbs/{article_id}{ext}"
    return None


def resolve_thumb(article):
    """(src, is_local). Prefers a locally generated thumbnail, falls back to the
    source article's own og:image (hotlinked), else (None, False)."""
    local = find_thumb(article["id"])
    if local:
        return local, True
    if article.get("src_image"):
        return article["src_image"], False
    return None, False


def render_gnb_pills():
    pills = ['<a class="pill-btn" data-cat="all" href="index.html">전체</a>']
    for key in CATEGORY_ORDER:
        pills.append(f'<a class="pill-btn" data-cat="{key}" href="index.html?cat={key}">{CATEGORY_LABEL[key]}</a>')
    return "".join(pills)


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
                        "src_image": item.get("image"),
                    })
    return articles


COMMENT_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>'


def render_feed_item(a, today_date):
    color = CATEGORY_COLOR[a["cat_key"]]
    emoji = "🌐" if a["region_key"] == "intl" else "🇰🇷"
    short_date = a["date"][5:].replace("-", ".")
    search_bits = esc_attr(" ".join([a["title"], strip_tags(a["insight"]), a["source"], a["dateLabel"]])).lower()

    thumb, _ = resolve_thumb(a)
    if thumb:
        thumb_html = f'<img src="{thumb}" alt="" loading="lazy">'
    else:
        thumb_html = f'<span class="feed-thumb-emoji">{CATEGORY_EMOJI.get(a["cat_key"], "📡")}</span>'

    new_badge = '<span class="badge-new">N</span>' if a["date"] == today_date else ""

    return f'''<article class="feed-item" data-cat="{a['cat_key']}" data-region="{a['region_key']}" data-id="{a['id']}" data-title="{esc_attr(a['title'])}" data-search="{search_bits}">
<a class="feed-row" href="{a['url']}" target="_blank" rel="noopener">
  <div class="feed-thumb" style="background:{color}22">{thumb_html}</div>
  <div class="feed-content">
    <div class="feed-top-row">
      <div class="feed-eyebrow"><span>{emoji}</span><span>{a['region']}</span></div>
      <span class="feed-hashtag">#{esc(a['cat_label'])}</span>
    </div>
    <div class="feed-title-row"><h2 class="feed-title">{a['title']}</h2>{new_badge}</div>
    <div class="feed-summary">{first_paragraph(a['insight'])}</div>
    <span class="comment-fab" role="button" tabindex="0" data-id="{a['id']}" data-title="{esc_attr(a['title'])}" aria-label="댓글 보기">{COMMENT_ICON_SVG}<span class="cc-num"></span><span class="badge-new comment-fab-new" style="display:none">N</span></span>
    <div class="feed-meta">
      <span class="feed-src-name">{esc(a['source'])}</span><span class="feed-dot">&middot;</span><span class="feed-date">{short_date}</span>
    </div>
  </div>
</a>
</article>'''


def render_rail(articles, limit=4):
    items = []
    for a in articles[:limit]:
        m = re.search(r"<b>(.*?)</b>", a["insight"])
        phrase = esc(m.group(1)) if m else esc(strip_tags(a["insight"])[:30])
        items.append(f'''<div class="rail-item">
<span class="rail-text" data-id="{a['id']}" data-title="{esc_attr(a['title'])}"><b>{phrase}</b><span class="rail-date">{a['dateLabel']}</span></span>
</div>''')
    return f'''<div class="rail-strip">
<h3>최근 핵심 인사이트</h3>
<div class="rail-grid">{"".join(items)}</div>
</div>'''


def build():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    days = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            days.append(json.load(f))
    days.sort(key=lambda d: d["intl"]["date"], reverse=True)

    articles = build_articles(days)

    # no more per-article detail pages — remove any left over from earlier builds
    if os.path.isdir(ARTICLES_DIR):
        shutil.rmtree(ARTICLES_DIR)

    today_date = articles[0]["date"] if articles else None
    feed_html = "".join(render_feed_item(a, today_date) for a in articles)
    rail_html = render_rail(articles)

    index_body = f'''<div class="wrap">
<header class="site">
<div class="header-row">
  <h1>UPLEAT 데일리 트렌드 아카이브</h1>
  <div class="region-tab-row" id="regionTabRow">
    <button class="region-tab-btn active" data-region="all">전체</button>
    <button class="region-tab-btn" data-region="domestic">국내</button>
    <button class="region-tab-btn" data-region="intl">해외</button>
  </div>
</div>
<p class="note">이 사이트는 매일 자동 수집되는 UPLEAT 데일리 트렌드 리포트(노션 데이터베이스)를 기사 단위로 미러링하며, 새 글이 생성될 때마다 자동으로 업데이트됩니다. 총 {len(articles)}개의 글 수록.</p>
</header>

<div class="feed-list" id="feedList">
{feed_html}
</div>
<div class="no-results" id="noResults" style="display:none">검색 결과가 없습니다.</div>
<div class="loadmore-wrap" id="loadMoreWrap"><button class="loadmore-btn" id="loadMoreBtn">더보기</button></div>

{rail_html}
</div>'''

    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(
            HEAD.format(title="UPLEAT 데일리 트렌드 아카이브", style=STYLE, gnb_pills=render_gnb_pills())
            + index_body
            + FEED_SCRIPT
            + COMMENT_PANEL_SCRIPT
            + AI_ASK_SCRIPT
            + FOOT.format(scrolltop=SCROLLTOP_SCRIPT)
        )

    print(f"Built index.html ({len(articles)} articles from {len(days)} day-files), no detail pages")


if __name__ == "__main__":
    build()
