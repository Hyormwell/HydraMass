#!/usr/bin/env python3
import asyncio
import pathlib
from hydra_reposter.core.client import telegram_client
from hydra_reposter.core.config import settings

async def is_authed(path):
    async with telegram_client(
        session_file=path,
        api_id=settings.api_id,
        api_hash=settings.api_hash,
    ) as cli:
        return await cli.is_user_authorized()

def main():
    base = pathlib.Path("sessions")
    for p in sorted(base.glob("*.session")):
        res = asyncio.run(is_authed(p))
        status = "AUTHORIZED" if res else "NOT AUTHORIZED"
        print(f"{p.name}: {status}")

if __name__ == "__main__":
    main()
