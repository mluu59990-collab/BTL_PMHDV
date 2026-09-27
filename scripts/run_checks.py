"""Run pytest against isolated MySQL databases using local .env credentials."""

import os
import subprocess
import sys
from pathlib import Path
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
env = os.environ | {
    k: v for k, v in dotenv_values(root / ".env").items() if v is not None
}
env["TEST_DATABASE_URL"] = env["DATABASE_URL"]
env["DEBUG"] = "false"
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests", "-q", "--tb=short"], cwd=root, env=env
)
sys.exit(result.returncode)
