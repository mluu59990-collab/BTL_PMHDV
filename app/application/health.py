from typing import Protocol


class DatabaseProbe(Protocol):
    async def ping(self) -> None: ...


async def check_readiness(database: DatabaseProbe) -> dict[str, str]:
    await database.ping()
    return {"status": "ok", "database": "ok"}
