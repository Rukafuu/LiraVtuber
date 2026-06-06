#!/usr/bin/env python3
"""
Remove slash órfãos/duplicados via REST (funciona com o bot Discord já ligado).

  python scripts/remover_duplicatas.py
  python scripts/remover_duplicatas.py --guild-id 123456789012345678
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import aiohttp
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from src.modules.discord.slash_meta import ORPHAN_SLASH_NAMES

API = "https://discord.com/api/v10"


async def _get_app_id(session: aiohttp.ClientSession, headers: dict) -> str:
    async with session.get(f"{API}/oauth2/applications/@me", headers=headers) as r:
        r.raise_for_status()
        return (await r.json())["id"]


async def _list(session, url: str, headers: dict) -> list:
    async with session.get(url, headers=headers) as r:
        r.raise_for_status()
        return await r.json()


async def _delete(session, url: str, headers: dict) -> None:
    async with session.delete(url, headers=headers) as r:
        if r.status not in (200, 204):
            text = await r.text()
            raise RuntimeError(f"DELETE {url} -> {r.status}: {text}")


async def purge_globals(session, headers, app_id: str) -> int:
    removed = 0
    for cmd in await _list(session, f"{API}/applications/{app_id}/commands", headers):
        if cmd.get("name") in ORPHAN_SLASH_NAMES:
            await _delete(session, f"{API}/applications/{app_id}/commands/{cmd['id']}", headers)
            print(f"  global: {cmd['name']}")
            removed += 1
    return removed


async def purge_guild_duplicates(session, headers, app_id: str, guild_id: str) -> int:
    global_names = {c["name"] for c in await _list(session, f"{API}/applications/{app_id}/commands", headers)}
    removed = 0
    base = f"{API}/applications/{app_id}/guilds/{guild_id}/commands"
    for cmd in await _list(session, base, headers):
        name = cmd.get("name")
        if name in global_names or name in ORPHAN_SLASH_NAMES:
            await _delete(session, f"{base}/{cmd['id']}", headers)
            print(f"  guild {guild_id}: {name}")
            removed += 1
    return removed


async def main(guild_id: str | None, guild_ids: list[str]) -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("DISCORD_TOKEN ausente no .env")
        sys.exit(1)
    headers = {"Authorization": f"Bot {token}"}

    async with aiohttp.ClientSession() as session:
        app_id = await _get_app_id(session, headers)
        print(f"Application ID: {app_id}")

        g_removed = await purge_globals(session, headers, app_id)
        print(f"Globais órfãos removidos: {g_removed}")

        if not guild_ids and guild_id:
            guild_ids = [guild_id]
        dup_total = 0
        for gid in guild_ids:
            dup_total += await purge_guild_duplicates(session, headers, app_id, gid)
        print(f"Duplicatas de servidor removidas: {dup_total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--guild-id", type=str, default=None)
    parser.add_argument(
        "--guild-ids",
        type=str,
        default=os.getenv("DISCORD_PURGE_GUILD_IDS", ""),
        help="IDs separados por vírgula (ou DISCORD_PURGE_GUILD_IDS no .env)",
    )
    args = parser.parse_args()
    ids = [x.strip() for x in args.guild_ids.split(",") if x.strip()]
    asyncio.run(main(args.guild_id, ids))