"""Scheduled entry point: start the MCP server as a subprocess over stdio,
discover its tools, and drive one listening cycle through them.

    python -m agent.run --trigger schedule
"""

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from agent.pipeline import run_cycle


class McpTools:
    def __init__(self, session: ClientSession):
        self.session = session

    async def call(self, name: str, **kwargs):
        res = await self.session.call_tool(name, kwargs)
        if res.isError:
            raise RuntimeError(f"tool {name} failed: {res.content[0].text if res.content else ''}")
        if res.structuredContent is not None:
            # FastMCP wraps non-object returns as {"result": ...}
            sc = res.structuredContent
            return sc["result"] if set(sc) == {"result"} else sc
        text = res.content[0].text if res.content else "null"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger", default="manual")
    ap.add_argument("--max-llm-calls", type=int, default=int(os.getenv("MAX_LLM_CALLS", "40")))
    args = ap.parse_args()

    params = StdioServerParameters(command=sys.executable, args=["-m", "listener_mcp.server"], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"[mcp] connected to ticmint-listener, {len(tools)} tools: {', '.join(t.name for t in tools)}")
            run = await run_cycle(McpTools(session), trigger=args.trigger, max_llm_calls=args.max_llm_calls)
    print(json.dumps(run, indent=2))
    # Fail the workflow only if every source failed: that's an outage, not a quiet day.
    return 1 if run["fetched"] == 0 and run["source_errors"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
