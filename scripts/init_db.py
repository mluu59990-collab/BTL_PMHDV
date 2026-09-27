"""Apply SQL to an existing MySQL database specified by DATABASE_URL / .env."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.infrastructure.db.bootstrap import apply_sql
from sqlalchemy.ext.asyncio import create_async_engine


async def main(dev_users):
    engine = create_async_engine(get_settings().database_url)
    try:
        await apply_sql(engine, dev_users=dev_users)
        print("MySQL schema and seeds applied.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-users", action="store_true")
    asyncio.run(main(parser.parse_args().dev_users))
