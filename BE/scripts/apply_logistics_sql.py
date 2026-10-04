"""Cài/cập nhật các bảng phụ và stored procedure Buổi 1, giữ dữ liệu nghiệp vụ.
MySQL DDL tự commit: đọc các file SQL trước khi chạy trên môi trường thật.
"""
import argparse
import asyncio
from pathlib import Path
import sys

from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

BE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BE))
from checks.run_features import sql_statements


async def apply(env):
    url=make_url(dotenv_values(env)['DATABASE_URL'])
    if url.database!='cms_logistics_core':
        raise SystemExit('Script này chỉ áp dụng cho cms_logistics_core. Kiểm tra DATABASE_URL.')
    engine=create_async_engine(url,connect_args={'init_command':"SET time_zone = '+00:00'"})
    try:
        async with engine.begin() as conn:
            columns=(await conn.exec_driver_sql('SHOW COLUMNS FROM users')).all()
            if 'role' not in {row[0] for row in columns}:
                raise SystemExit('Bảng users chưa phải schema logistics: thiếu cột role.')
            await conn.exec_driver_sql('SET sql_notes=0')
            for path in sorted((BE.parent/'sql').glob('[0-9][0-9]_*.sql')):
                for statement in sql_statements(path):
                    await conn.exec_driver_sql(statement)
                print('Đã áp dụng:',path.name)
    finally:
        await engine.dispose()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--env',type=Path,default=BE/'.env')
    asyncio.run(apply(parser.parse_args().env))
