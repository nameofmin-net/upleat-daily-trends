#!/usr/bin/env python3
"""UPLEAT 데일리 트렌드 — 카테고리 전문가(Claude) 댓글 등록기.

리서치 루틴이 [3.5단계]에서 실행한다.
  python3 tools/post_comments.py data/YYYY-MM-DD.json /tmp/claude_comments.json

- 댓글 JSON: {"기사ID": "댓글", ...}  (기사ID 예: 2026-11-26-i-ux-2 — build.py와 같은 규칙)
- 이름은 카테고리별 페르소나 + "· Claude"로 자동으로 붙는다 (AI 댓글임을 표시).
- 같은 기사에 같은 이름의 댓글이 이미 있으면 건너뛴다 (재실행해도 중복 없음).
- 60자를 넘거나 오늘자 데이터에 없는 기사ID는 등록하지 않는다.
"""
import json
import sys
import time
import urllib.parse
import urllib.request

API = "https://upleat-trend-comments.dkdldb3144.workers.dev/api/comments"
ORIGIN = "https://nameofmin-net.github.io"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
PERSONA = {"ai": "AI 리서처", "ux": "UX 리서처", "design": "디자인 디렉터", "biz": "테크 애널리스트"}
LABEL = "Claude"
MAX_LEN = 60


def article_ids(day):
    ids = {}
    date = day["intl"]["date"]
    for region_key, short in (("intl", "i"), ("domestic", "d")):
        for cat in day[region_key]["categories"]:
            kept = 0
            for item in cat["items"]:
                if item.get("duplicate"):
                    continue
                kept += 1
                ids[f"{date}-{short}-{cat['key']}-{kept}"] = cat["key"]
    return ids


def request(url, data=None):
    headers = {"Origin": ORIGIN, "User-Agent": UA}
    if data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def main():
    data_path, comments_path = sys.argv[1], sys.argv[2]
    ids = article_ids(json.load(open(data_path, encoding="utf-8")))
    comments = json.load(open(comments_path, encoding="utf-8"))
    posted = skipped = 0
    for aid, body in comments.items():
        body = str(body).strip()
        if aid not in ids:
            print(f"[건너뜀] 오늘자 데이터에 없는 ID: {aid}")
            skipped += 1
            continue
        if not body or len(body) > MAX_LEN:
            print(f"[건너뜀] 길이 {len(body)}자 (최대 {MAX_LEN}): {aid}")
            skipped += 1
            continue
        name = f"{PERSONA[ids[aid]]} · {LABEL}"
        try:
            existing = request(API + "?page=" + urllib.parse.quote(aid)).get("comments", [])
            if any(c.get("name") == name for c in existing):
                print(f"[건너뜀] 이미 있음: {aid}")
                skipped += 1
                continue
            res = request(API, {"page": aid, "name": name, "body": body})
            if res.get("ok"):
                posted += 1
            else:
                print(f"[실패] {aid}: {res}")
        except Exception as e:  # 한 건 실패해도 나머지는 계속
            print(f"[실패] {aid}: {e}")
        time.sleep(0.2)
    print(f"등록 {posted}건 / 건너뜀 {skipped}건 / 전체 {len(comments)}건")


if __name__ == "__main__":
    main()
