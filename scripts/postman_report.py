"""Produce a readable, searchable report without JWTs or passwords."""

import csv
import html
import json
import re
import sys
from pathlib import Path

folder = Path(sys.argv[1])
raw = json.loads((folder / "newman.private.json").read_text())


def clean(value):
    if isinstance(value, dict):
        return {
            k: (
                "[REDACTED]"
                if any(x in k.lower() for x in ("password", "token", "authorization"))
                else clean(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str):
        return re.sub(
            r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
            "[REDACTED JWT]",
            value,
        )
    return value


def decode_body(response):
    stream = response.get("stream", {})
    value = (
        bytes(stream.get("data", [])).decode("utf-8", errors="replace")
        if isinstance(stream, dict)
        else str(stream)
    )
    try:
        return clean(json.loads(value))
    except ValueError:
        return clean(value)


def request_body(request):
    body = request.get("body", {})
    if body.get("mode") == "raw":
        try:
            return clean(json.loads(body.get("raw", "")))
        except ValueError:
            return clean(body.get("raw", ""))
    if body.get("mode") == "urlencoded":
        return clean({x["key"]: x.get("value") for x in body.get("urlencoded", [])})
    return None


rows = []
for run in raw["run"]["executions"]:
    request = run["request"]
    response = run.get("response") or {}
    url = request["url"]
    path = "/" + "/".join(url.get("path", [])) if isinstance(url, dict) else url
    query = url.get("query", []) if isinstance(url, dict) else []
    asserts = run.get("assertions", [])
    passed = (
        all(not x.get("error") for x in asserts) and bool(response) and bool(asserts)
    )
    expected = re.search(r"\[(\d+)\]$", run["item"]["name"])
    rows.append(
        dict(
            name=run["item"]["name"],
            method=request["method"],
            path=path,
            query=query,
            expected=int(expected[1]) if expected else None,
            status=response.get("code"),
            ms=response.get("responseTime"),
            passed=passed,
            input=request_body(request),
            response=decode_body(response),
            errors=[x["error"].get("message") for x in asserts if x.get("error")],
        )
    )
summary = {
    "requests": len(rows),
    "passed": sum(x["passed"] for x in rows),
    "failed": sum(not x["passed"] for x in rows),
    "negative_cases": sum((x["expected"] or 0) >= 400 for x in rows),
    "database": (folder / "database.txt").read_text().strip(),
}
(folder / "results.json").write_text(
    json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2)
)
with (folder / "results.csv").open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "name",
            "method",
            "path",
            "expected",
            "status",
            "ms",
            "passed",
            "input",
            "response",
            "errors",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                k: json.dumps(row[k], ensure_ascii=False)
                if isinstance(row[k], (list, dict))
                else row[k]
                for k in writer.fieldnames
            }
        )
body = []
for row in rows:
    title = f"{'PASS' if row['passed'] else 'FAIL'} · {row['method']} {row['path']} · {row['name']} · thực tế {row['status']} · {row['ms']} ms"
    body.append(
        '<details class="'
        + ("pass" if row["passed"] else "fail")
        + '"><summary>'
        + html.escape(title)
        + "</summary><pre>"
        + html.escape(
            json.dumps(
                {
                    k: row[k]
                    for k in (
                        "query",
                        "input",
                        "expected",
                        "status",
                        "response",
                        "errors",
                    )
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        + "</pre></details>"
    )
(folder / "report.html").write_text(
    """<!doctype html><html lang="vi"><meta charset="utf-8"><title>CMS – Báo cáo kiểm thử API</title><style>body{font:15px system-ui;max-width:1200px;margin:30px auto;padding:16px}summary{padding:12px;cursor:pointer}.pass{border-left:4px solid #16814a}.fail{border-left:4px solid #d12c31}details{margin:8px 0;background:#f3f5f7}pre{white-space:pre-wrap;padding:16px}input{padding:12px;width:70%}button{padding:12px}</style><h1>CMS MySQL — Kết quả chạy API thực tế</h1><p>"""
    + html.escape(json.dumps(summary, ensure_ascii=False))
    + """</p><p>Ca nhập sai trả đúng lỗi mong đợi vẫn là PASS. FAIL là kết quả khác kỳ vọng; cần đọc chi tiết để phân biệt lỗi API và lỗi test.</p><input id="q" placeholder="Tìm API / tên ca kiểm thử"><button onclick="onlyFail=!onlyFail;filter()">Bật/tắt chỉ ca FAIL</button>"""
    + "".join(body)
    + """<script>let onlyFail=false;function filter(){let q=document.querySelector('#q').value.toLowerCase();document.querySelectorAll('details').forEach(d=>d.hidden=!d.textContent.toLowerCase().includes(q)||(onlyFail&&!d.classList.contains('fail')))}document.querySelector('#q').oninput=filter;</script></html>"""
)
print(json.dumps(summary, ensure_ascii=False))
# Raw export contains short-lived credentials. Keep it local and ignored by git.
(folder / "newman.private.json").chmod(0o600)
