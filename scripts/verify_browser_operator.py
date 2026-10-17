"""Opt-in real website probe through Adex's isolated broker. No accounts or side effects."""

import argparse
import asyncio
import json
import re
from pathlib import Path
from adex_tools.browser.process import BrowserProcess
from adex_tools.browser.login import access_block, login_form


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output")
    parser.add_argument("--query", default="")
    parser.add_argument("--open-login", action="store_true")
    args = parser.parse_args()
    actor = await BrowserProcess.start()
    try:
        value = await actor.call({"url": args.url})
        for _ in range(4):
            if value.get("pending") or access_block(value):
                break
            await asyncio.sleep(0.5)
            value = await actor.call({"action": "observe"})
        if (
            args.open_login
            and not value.get("pending")
            and not access_block(value)
            and not login_form(value)
        ):
            entry = next(
                (
                    n
                    for n in value.get("nodes", [])
                    if n.get("id")
                    and n.get("role") in ("button", "textbox")
                    and re.search(r"登录|sign in|log in", n.get("name", ""), re.I)
                ),
                None,
            )
            if entry:
                value = await actor.call(
                    {
                        "action": "click",
                        "element_id": entry["id"],
                        "observation_id": value["observation_id"],
                    }
                )
                for _ in range(4):
                    if value.get("pending") or login_form(value) or access_block(value):
                        break
                    await asyncio.sleep(0.5)
                    value = await actor.call({"action": "observe"})
        search_attempted = False
        if (
            args.query
            and not value.get("pending")
            and not access_block(value)
            and not login_form(value)
        ):
            field = next(
                (
                    n
                    for n in value.get("nodes", [])
                    if n.get("id")
                    and n.get("role") in ("textbox", "searchbox", "combobox")
                    and not n.get("protected")
                    and re.search(r"搜索|查询|search", n.get("name", ""), re.I)
                ),
                None,
            )
            if field:
                search_attempted = True
                value = await actor.call(
                    {
                        "action": "type",
                        "element_id": field["id"],
                        "text": args.query[:200],
                        "observation_id": value["observation_id"],
                    }
                )
                if not value.get("pending"):
                    value = await actor.call(
                        {
                            "action": "key",
                            "element_id": field["id"],
                            "text": "Enter",
                            "observation_id": value["observation_id"],
                        }
                    )
                    for _ in range(4):
                        if (
                            value.get("pending")
                            or access_block(value)
                            or login_form(value)
                        ):
                            break
                        await asyncio.sleep(0.5)
                        value = await actor.call({"action": "observe"})
        report = {
            "url": value.get("url"),
            "search_attempted": search_attempted,
            "search_controls": [
                {"role": n["role"], "name": n.get("name", "")}
                for n in value.get("nodes", [])
                if n.get("role") in ("textbox", "searchbox", "combobox")
            ][:10],
            "title": value.get("title"),
            "nodes": len(value.get("nodes", [])),
            "login_form_available": bool(login_form(value)),
            "access_block": access_block(value),
            "network": value.get("network"),
            "pending_request": (value.get("pending") or {})
            .get("preview", {})
            .get("destination"),
            "availability": "BLOCKED_EXTERNAL"
            if access_block(value) or not value.get("nodes")
            else "LOGIN_REQUIRED"
            if login_form(value)
            else "APPROVAL_REQUIRED"
            if value.get("pending")
            else "PAGE_OBSERVED_UNVERIFIED",
        }
    except Exception as error:
        report = {
            "availability": "BLOCKED_EXTERNAL"
            if hasattr(error, "detail")
            else "DIAGNOSTIC_ERROR",
            "code": str(getattr(error, "detail", type(error).__name__)),
        }
    finally:
        await actor.close()
    if args.output:
        path = Path(args.output)
        if ".local-data" not in path.parts:
            raise SystemExit(
                "Probe reports belong in ignored .local-data, not public source"
            )
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
