#!/usr/bin/env python3
"""Generate an in-site minutes-excerpt (会議録抜粋) page from the NDL speech API.

Usage: make-full-minutes.py <issueID> <startOrder> <endOrder> <output_filename.html> <page_title> <intro_html>

Fetches all speech records for the issue via https://kokkai.ndl.go.jp/api/1.0/speech,
selects speechOrder in [startOrder, endOrder], and wraps them in the same template
style as the note-based full pages (search bar + party colors). The full text is
handled entirely in this script; afterwards every body paragraph is verified
verbatim against the API text and only counts are printed.
"""
import sys, re, json, html, urllib.request, urllib.parse

def fetch_all(issue_id):
    recs, start = [], 1
    while True:
        params = {"issueID": issue_id, "recordPacking": "json",
                  "maximumRecords": "100", "startRecord": str(start)}
        url = "https://kokkai.ndl.go.jp/api/1.0/speech?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
        recs.extend(data["speechRecord"])
        nxt = data.get("nextRecordPosition")
        if not nxt:
            return recs
        start = int(nxt)

def norm(s):
    return re.sub(r"\s+", "", s or "")

def main():
    issue_id, start_o, end_o, out_name, title, intro = sys.argv[1:7]
    start_o, end_o = int(start_o), int(end_o)
    txt_url = f"https://kokkai.ndl.go.jp/txt/{issue_id}/{start_o}"
    recs = fetch_all(issue_id)
    seg = [r for r in recs if r.get("speechOrder") and start_o <= int(r["speechOrder"]) <= end_o]
    seg.sort(key=lambda r: int(r["speechOrder"]))
    assert seg, "no records in range"
    assert int(seg[0]["speechOrder"]) == start_o and int(seg[-1]["speechOrder"]) == end_o, \
        f"range edges mismatch: {seg[0]['speechOrder']}..{seg[-1]['speechOrder']}"

    parts, all_text = [], []
    for r in seg:
        speech = r["speech"]
        all_text.append(speech)
        # Heading from the ○ marker at the head of the speech text.
        m = re.match(r"\s*○([^　\r\n]+)[　]", speech)
        heading = m.group(1) if m else (r.get("speaker") or "")
        parts.append(f"<h2>{html.escape(heading)}</h2>")
        body = speech
        if m:
            body = body[body.index("　", m.start()) + 1:]
        for para in re.split(r"[\r\n]+", body):
            para = para.strip("　 \t")
            if para:
                parts.append(f"<p>{html.escape(para)}</p>")
    body_html = "\n".join(parts)

    # Read the note-based template out of make-full.py and adapt it.
    src = open("make-full.py", encoding="utf-8").read()
    template = src.split('TEMPLATE = """', 1)[1].split('"""', 1)[0]
    page = template.replace("{title}", title).replace("{body}", body_html).replace("{note_url}", txt_url)
    page = page.replace(
        '<p class="note-line">全文文字起こし（出典：note「国民民主党の文字起こしをする鶴亀（非公式）」／このサイトは非公式の要約・転載ページです）</p>',
        '<p class="note-line">会議録抜粋（出典：国会会議録検索システム／このサイトは非公式の要約ページです）</p>')
    page = page.replace(
        f'<p><a href="{txt_url}" target="_blank" rel="noopener">noteでも読む（元記事）</a></p>',
        f'<p><a href="{txt_url}" target="_blank" rel="noopener">国会会議録で全文を読む（公式）</a></p>')
    page = page.replace('<div id="articleBody">\n', '<div id="articleBody">\n<p>' + intro + '</p>\n', 1)

    with open("full/" + out_name, "w", encoding="utf-8") as f:
        f.write(page)

    # Verbatim verification: every excerpt paragraph must appear in the API text.
    api_norm = norm("".join(all_text))
    paras = re.findall(r"<p>(.*?)</p>", body_html)
    ok = sum(1 for p in paras if norm(html.unescape(p)) in api_norm)
    print(f"records {len(seg)} ({seg[0]['speechOrder']}..{seg[-1]['speechOrder']}), "
          f"paragraphs {len(paras)}, verbatim-ok {ok}, page chars {len(page)}")
    assert ok == len(paras), "some paragraphs do not match the API text verbatim"

if __name__ == "__main__":
    main()
