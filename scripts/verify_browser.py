"""Opt-in real public Chromium read; no DB, account, key or model call.

uv run --project services/adex-tools python scripts/verify_browser.py
"""

import argparse
import asyncio
import json
from adex_tools.runners.browser import read_page
from fastapi import HTTPException


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://docs.python.org/3/")
    parser.add_argument("--query", default="documentation")
    parser.add_argument("--max-pages", type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    try:
        result = await read_page(args.url, args.query, args.max_pages)
    except HTTPException as error:
        raise SystemExit(f"BLOCKED_EXTERNAL: {error.detail}") from None
    if result.get("provider") != "chromium" or not result.get("items"):
        raise SystemExit("BLOCKED_EXTERNAL: no real rendered page obtained")
    print(
        json.dumps(
            {
                "provider": result["provider"],
                "pages": [
                    {
                        key: item[key]
                        for key in ("url", "title", "fetched_at", "evidence_level")
                    }
                    | {"text_chars": len(item["extracted_text"])}
                    for item in result["items"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
