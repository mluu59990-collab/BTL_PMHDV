"""Compare executed requests to every documented API method and catalog kind."""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DEBUG"] = "false"
from app.main import app  # noqa: E402 — standalone script adds project root

folder = Path(sys.argv[1])
report = json.loads((folder / "results.json").read_text())
routes = []
for path, operations in app.openapi()["paths"].items():
    paths = (
        [
            path.replace("{kind}", kind)
            for kind in ("countries", "units", "package-types", "categories")
        ]
        if "{kind}" in path
        else [path]
    )
    for expanded in paths:
        for method in operations:
            if method not in ("get", "post", "patch", "delete", "put"):
                continue
            pattern = "^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(expanded)) + "$"
            routes.append(
                {
                    "method": method.upper(),
                    "path": expanded,
                    "pattern": pattern,
                    "requests": 0,
                    "passed": 0,
                }
            )
routes.sort(key=lambda x: x["path"].count("{"))
unmatched = []
for case in report["cases"]:
    for route in routes:
        if route["method"] == case["method"] and re.match(
            route["pattern"], case["path"]
        ):
            route["requests"] += 1
            route["passed"] += int(case["passed"])
            break
    else:
        unmatched.append(case["method"] + " " + case["path"])
short = [r for r in routes if r["requests"] < 10]
lines = [
    "# Độ phủ lượt kiểm thử API",
    "",
    f"{len(routes)} API (tính riêng từng loại catalog); {len(report['cases'])} request thực tế.",
    "",
    "| Method | API | Lượt chạy | PASS |",
    "|---|---|---:|---:|",
]
for route in sorted(routes, key=lambda r: (r["path"], r["method"])):
    lines.append(
        f"| {route['method']} | `{route['path']}` | {route['requests']} | {route['passed']} |"
    )
(folder / "coverage.md").write_text("\n".join(lines) + "\n")
print(
    json.dumps(
        {
            "apis": len(routes),
            "requests": len(report["cases"]),
            "minimum_requests_per_api": min(r["requests"] for r in routes),
            "under_10": short,
            "unmatched": unmatched,
        },
        ensure_ascii=False,
    )
)
if short or unmatched:
    sys.exit(1)
