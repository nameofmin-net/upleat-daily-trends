import sys, re, json, glob, os

def unescape(text):
    text = text.replace('\\\\"', '\\"')
    text = re.sub(r'\\([<>#_*\[\]!&])', r'\1', text)
    return text

def parse_one(path):
    date = os.path.basename(path).replace("raw_text_", "").replace(".txt", "")
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    text = unescape(raw)
    m = re.search(r'<script type="application/json" id="daysData">\s*(\[.*\])\s*</script>', text, re.DOTALL)
    if not m:
        print(f"FAIL {date}: daysData script not found")
        return False
    json_text = m.group(1)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"FAIL {date}: JSON parse error: {e}")
        # print context around error
        pos = e.pos
        print("context:", repr(json_text[max(0,pos-80):pos+80]))
        return False
    intl = None
    domestic = None
    for obj in data:
        if obj.get("region") == "해외":
            intl = obj
        elif obj.get("region") == "국내":
            domestic = obj
    if intl is None or domestic is None:
        print(f"FAIL {date}: missing region(s): {[o.get('region') for o in data]}")
        return False
    for label, obj in [("intl", intl), ("domestic", domestic)]:
        cats = obj.get("categories", [])
        keys = [c.get("key") for c in cats]
        if keys != ["ai", "ux", "design", "biz"]:
            print(f"FAIL {date}: {label} category keys wrong: {keys}")
            return False
    full_date = intl.get("date", date)
    out = {"intl": intl, "domestic": domestic}
    outpath = f"data/{full_date}.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    n_items = sum(len(c["items"]) for c in intl["categories"]) + sum(len(c["items"]) for c in domestic["categories"])
    print(f"OK {full_date} -> {outpath} ({n_items} items)")
    return True

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        args = sorted(glob.glob("raw_text_*.txt"))
    ok, fail = 0, 0
    for p in args:
        if parse_one(p):
            ok += 1
        else:
            fail += 1
    print(f"\n{ok} ok, {fail} failed")
