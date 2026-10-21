"""Starts the real MCP server over stdio (offline fixture mode), runs a full cycle
through the client, and checks what lands on disk. Runs twice to prove de-duplication."""

import asyncio
import csv
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from agent.pipeline import run_cycle
from agent.run import McpTools

ROOT = Path(__file__).resolve().parent.parent


async def _cycle(env):
    params = StdioServerParameters(command=sys.executable, args=["-m", "listener_mcp.server"], env=env, cwd=str(ROOT))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            assert {"search_source", "qualify_post", "sync_sheet", "query_leads"} <= names
            return await run_cycle(McpTools(session), trigger="test", log=lambda *_: None)


def test_full_cycle(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LLM_", "GOOGLE_", "SHEET_"))}
    env |= {"LISTENER_FIXTURES": str(ROOT / "tests/fixtures/posts.json"), "LISTENER_DATA_DIR": str(tmp_path),
            "PYTHONPATH": str(ROOT)}
    run1 = asyncio.run(_cycle(env))
    assert run1["discovered"] == 8 and run1["new"] == 8
    leads = list(csv.DictReader((tmp_path / "leads.csv").open()))
    ids = {l["lead_id"] for l in leads}
    assert {"reddit:fx1", "hackernews:fx2", "reddit:fx5", "reddit:fx6"} <= ids
    assert not ids & {"reddit:fx3", "hackernews:fx4", "reddit:fx7", "reddit:fx8"}
    assert run1["sheet_status"].startswith("skipped")

    run2 = asyncio.run(_cycle(env))
    assert run2["new"] == 0 and run2["qualified"] == 0
    assert len(list(csv.DictReader((tmp_path / "runs.csv").open()))) == 2
