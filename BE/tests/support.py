"""Hỗ trợ test trên database tạm và chạy collection qua HTTP local."""

import asyncio
import os
import shutil
import socket
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def statements(path):
    delimiter, buffer = ";", ""
    for line in path.read_text().splitlines():
        if line.strip().upper().startswith("DELIMITER "):
            delimiter = line.strip().split()[1]
            continue
        if not line.strip() or line.lstrip().startswith("--"):
            continue
        buffer += line + "\n"
        if buffer.rstrip().endswith(delimiter):
            statement = buffer.rstrip()[: -len(delimiter)].strip()
            buffer = ""
            if not statement.upper().startswith("USE "):
                yield statement
    if buffer.strip():
        raise ValueError(f"SQL chưa kết thúc: {path}")


class Stream(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body

    async def __aiter__(self):
        yield self.body


class BackendTransport(httpx.AsyncBaseTransport):
    def __init__(self, backend):
        self.backend = backend

    async def handle_async_request(self, request):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.backend)) as client:
            response = await client.send(request)
            return httpx.Response(
                response.status_code, headers=response.headers, stream=Stream(response.content)
            )


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def run_postman(collection_name):
    """Start isolated servers using the caller's temporary DATABASE_URL."""
    if not shutil.which("postman"):
        raise RuntimeError("Postman CLI chưa được cài")
    backend_port = free_port()
    gateway_port = free_port()
    while gateway_port == backend_port:
        gateway_port = free_port()
    env = {**os.environ, "BACKEND_URL": f"http://127.0.0.1:{backend_port}"}
    processes = []
    cli = None
    with (
        tempfile.TemporaryDirectory(prefix="logistics-http-check-") as folder,
        ExitStack() as stack,
    ):
        try:
            for directory, module, port in [
                ("BE", "app.main:app", backend_port),
                ("Gateway", "gateway_app.main:app", gateway_port),
            ]:
                log = stack.enter_context(
                    await asyncio.to_thread(Path(folder, f"{directory}.log").open, "w+")
                )
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "uvicorn",
                    module,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "warning",
                    cwd=ROOT / directory,
                    env=env,
                    stdout=log,
                    stderr=log,
                )
                processes.append(process)
            async with httpx.AsyncClient(timeout=1) as client:
                deadline = time.monotonic() + 20
                while True:
                    if any(process.returncode is not None for process in processes):
                        raise RuntimeError("HTTP test server không khởi động được")
                    try:
                        response = await client.get(f"http://127.0.0.1:{gateway_port}/health")
                        if response.status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError("Timeout chờ HTTP test server")
                    await asyncio.sleep(0.1)
            cli = await asyncio.create_subprocess_exec(
                "postman",
                "collection",
                "run",
                str(ROOT / "Gateway/postman" / collection_name),
                "--env-var",
                f"base_url=http://127.0.0.1:{gateway_port}",
                "--env-var",
                "admin_username=admin",
                "--env-var",
                "admin_password=Strong@123456",
                "--no-report-events",
                cwd=ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output, _ = await asyncio.wait_for(cli.communicate(), timeout=90)
            print(output.decode(errors="replace"))
            if cli.returncode:
                raise AssertionError(f"Postman CLI failed: {cli.returncode}")
        finally:
            if cli is not None and cli.returncode is None:
                cli.kill()
                await cli.wait()
            for process in processes:
                if process.returncode is None:
                    process.terminate()
            for process in processes:
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    process.kill()
                    await process.wait()
