"""Run the Postman collection locally against a fresh, isolated MySQL database.

Keeps the test database for inspection; never writes API test records to the app DB.
Run `python scripts/run_postman.py --serve` to keep that API available afterwards.
"""

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.infrastructure.db.bootstrap import apply_sql  # noqa: E402 — standalone script adds project root


async def prepare(url):
    admin = create_async_engine(url.set(database=""), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.exec_driver_sql(
                f"CREATE DATABASE `{url.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        await admin.dispose()
    engine = create_async_engine(url)
    try:
        await apply_sql(engine, dev_users=True)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--newman",
        default=shutil.which("newman")
        or "/private/tmp/btl-postman/node_modules/.bin/newman",
    )
    args = parser.parse_args()
    env = os.environ | {
        k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None
    }
    env["DEBUG"] = "false"
    url = make_url(env["DATABASE_URL"]).set(
        database="cms_postman_" + uuid.uuid4().hex[:12]
    )
    env["DATABASE_URL"] = url.render_as_string(hide_password=False)
    asyncio.run(prepare(url))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = ROOT / "reports" / stamp
    out.mkdir(parents=True)
    (out / "database.txt").write_text(url.database + "\n")
    print("Test database:", url.database, flush=True)
    log = (out / "server.log").open("w")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(100):
            if server.poll() is not None:
                raise RuntimeError("Server exited; inspect " + str(out / "server.log"))
            try:
                if (
                    httpx.get(
                        f"http://127.0.0.1:{args.port}/health", timeout=1
                    ).status_code
                    == 200
                ):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError("Server startup timed out")
        # Verify the socket belongs to the launched process before sending mutations.
        time.sleep(0.3)
        if server.poll() is not None:
            raise RuntimeError("Port already in use; refusing to test another server")
        result = subprocess.run(
            [
                args.newman,
                "run",
                str(ROOT / "postman/CMS.postman_collection.json"),
                "--env-var",
                f"base_url=http://127.0.0.1:{args.port}",
                "--reporters",
                "cli,json",
                "--reporter-cli-no-assertions",
                "--reporter-json-export",
                str(out / "newman.private.json"),
                "--timeout-request",
                "10000",
            ],
            cwd=ROOT,
            stdout=(out / "newman.log").open("w"),
            stderr=subprocess.STDOUT,
            check=False,
        )
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/postman_report.py"), str(out)],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/audit_postman.py"), str(out)],
            cwd=ROOT,
            env=env,
            check=True,
        )
        print(
            "Report:",
            out / "report.html",
            "Newman exit:",
            result.returncode,
            flush=True,
        )
        if args.serve:
            print(
                f"API remains available at http://127.0.0.1:{args.port}/docs. Ctrl+C to stop.",
                flush=True,
            )
            server.wait()
        return result.returncode
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
