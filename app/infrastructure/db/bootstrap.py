"""Apply ordered MySQL SQL files without splitting semicolons inside strings."""

from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[3] / "sql"


def statements(source):
    current, quote, comment, escaped = [], None, False, False
    index = 0
    while index < len(source):
        char = source[index]
        if comment:
            if char == "\n":
                comment = False
                current.append(char)
        elif quote:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                if index + 1 < len(source) and source[index + 1] == quote:
                    current.append(source[index + 1])
                    index += 1
                else:
                    quote = None
        elif source[index : index + 2] == "--":
            comment = True
            index += 1
        elif char in "'\"`":
            quote = char
            current.append(char)
        elif char == ";":
            if "".join(current).strip():
                yield "".join(current).strip()
            current = []
        else:
            current.append(char)
        index += 1
    if "".join(current).strip():
        yield "".join(current).strip()


async def apply_sql(engine, *, dev_users=False, files=None):
    files = files or sorted(SQL_DIR.glob("*.sql"))
    async with engine.connect() as connection:
        for path in files:
            if path.name == "03_seed_dev_users.sql" and not dev_users:
                continue
            for statement in statements(path.read_text()):
                await connection.exec_driver_sql(statement)
        await connection.commit()
