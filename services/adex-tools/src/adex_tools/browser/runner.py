"""Credential-free controlled Chromium broker. JSON IPC is not exposed to models.

Trusted fixed CDP operations only; handles refer to the current AX snapshot. Every
Agent-mode mutating request is held before dispatch and can only be released by the
parent after its durable approval/effect gate. Human takeover is explicit and exclusive.
"""

import asyncio
import base64
import hashlib
import json
import re
import sys
from uuid import uuid4
from urllib.parse import urlsplit
from adex_tools.browser.policy import SECRET, CRITICAL, request_digest, request_preview, receipt_id
from adex_tools.runners.browser_policy import admitted_hosts, allowed_url, resolve_public_hosts
from adex_tools.runners.browser_proxy import BrowserEgress


class Broker:
    def __init__(self):
        self.mode = "AGENT"
        self.human_authorized = False
        self.human_until = 0
        self.handles = {}
        self.revision = ""
        self.pending = None
        self.last_receipt = None
        self.private_values = set()
        self.secret_values = set()
        self.critical = False
        self.dialog = None
        self.dialog_id = None
        self.last_view = None
        self.tabs = {}
        self.requests = 0
        self.gesture = ""

    def safe(self, value):
        text = str(value)[:16000]
        for secret in self.private_values:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        return text

    async def admit(self, url):
        host = urlsplit(url).hostname
        if host in self.pinned:
            return allowed_url(url, self.pinned)
        try:
            hosts = admitted_hosts(url)
            values = await asyncio.wait_for(asyncio.to_thread(resolve_public_hosts, (host,)), 4)
            if host not in hosts or host not in values or len(self.pinned) >= 32:
                return False
            self.pinned.update(values)
            return True
        except Exception:
            return False

    async def forward(self, route):
        if self.test_fixture:
            from adex_tools.browser.fixture import HTML, LOGIN_HTML

            if (
                route.request.method == "GET"
                and urlsplit(route.request.url).path == "/fixture-login"
                and "adex_fixture=TEST_FIXTURE_SESSION" in route.request.headers.get("cookie", "")
            ):
                return await route.fulfill(status=200, content_type="text/html", body=HTML)
            if route.request.method == "POST" and urlsplit(route.request.url).path == "/login":
                return await route.fulfill(
                    status=200,
                    content_type="application/json",
                    headers={
                        "Set-Cookie": "adex_fixture=TEST_FIXTURE_SESSION; Path=/; Secure; HttpOnly; SameSite=Lax"
                    },
                    body='{"authenticated":true}',
                )
            if route.request.method == "POST":
                return await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {"accepted": True}
                        if "FIXTURE_UNKNOWN" in (route.request.post_data or "")
                        else {
                            "note_id": "TEST_FIXTURE_NOTE_001",
                            "note_url": "https://example.com/note/TEST_FIXTURE_NOTE_001",
                        }
                    ),
                )
            return await route.fulfill(
                status=200,
                content_type="text/html",
                body=(
                    '<html><iframe title="登录" style="width:600px;height:500px" src="https://example.com/fixture-login"></iframe></html>'
                    if urlsplit(route.request.url).path == "/fixture-login-frame"
                    else LOGIN_HTML
                    if urlsplit(route.request.url).path == "/fixture-login"
                    else HTML
                ),
            )
        if self.mode == "AGENT" and route.request.method not in ("GET", "HEAD", "OPTIONS"):
            # Browser redirects can skip the original route handler. Dispatch one
            # approved request only; never replay a POST body at another URL.
            response = await route.fetch(max_redirects=0, max_retries=0, timeout=10000)
            if 300 <= response.status < 400:
                headers = {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() not in ("location", "content-length", "content-encoding")
                }
                return await route.fulfill(
                    status=response.status, headers=headers, body=await response.body()
                )
            return await route.fulfill(response=response)
        return await route.continue_()

    async def intercept(self, route):
        request = route.request
        if self.test_fixture and urlsplit(request.url).hostname != "example.com":
            return await route.abort()
        self.requests += 1
        if self.requests > 1000 or not await self.admit(request.url):
            return await route.abort()
        if request.resource_type in ("media", "font") or (
            self.mode == "AGENT" and request.resource_type == "ping"
        ):
            return await route.abort()
        # An unsolicited cross-origin write on page load is not a user action.
        # Deny it rather than turning telemetry/bootstrap traffic into a publish
        # approval. Never grant a write or treat the denied request as success.
        if (
            self.mode == "AGENT"
            and not self.gesture
            and request.method not in ("GET", "HEAD", "OPTIONS")
            and urlsplit(request.url).hostname != urlsplit(self.page.url).hostname
        ):
            return await route.abort()
        new_domain = urlsplit(request.url).hostname not in self.read_hosts and request.resource_type not in (
            "image",
            "stylesheet",
            "script",
        )
        needs_approval = (
            new_domain
            or request.method not in ("GET", "HEAD", "OPTIONS")
            or (self.critical and request.is_navigation_request())
        )
        if (
            self.mode == "HUMAN"
            and self.human_authorized
            and asyncio.get_running_loop().time() < self.human_until
        ) or not needs_approval:
            return await self.forward(route)
        if self.pending:
            return await route.abort()
        data = request.post_data_buffer or b""
        if len(data) > 8 * 1024 * 1024:
            return await route.abort()
        future = asyncio.get_running_loop().create_future()
        token = str(uuid4())
        self.pending = {
            "id": token,
            "digest": request_digest(request.url, request.method, data),
            "preview": request_preview(
                request.url, request.method, data, request.headers.get("content-type", "")
            ),
            "gesture": self.safe(self.gesture),
            "grant_read_host": urlsplit(request.url).hostname
            if new_domain and request.method == "GET"
            else None,
            "transport_only": not CRITICAL.search(self.gesture)
            and bool(
                re.search(
                    r"搜索|查询|上传(?:图片|文件)?|保存草稿|search|upload|save draft", self.gesture, re.I
                )
            ),
            "future": future,
            "request": request,
        }
        if self.pending.get("grant_read_host"):
            self.pending["preview"]["additional_permission"] = {
                "scope": "READ_HOST_FOR_THIS_TASK",
                "host": self.pending["grant_read_host"],
            }
            self.pending["transport_only"] = True
        try:
            decision = await asyncio.wait_for(future, 900)
            if decision:
                if self.pending.get("grant_read_host"):
                    self.read_hosts.add(self.pending["grant_read_host"])
                await self.forward(route)
            else:
                await route.abort()
        except Exception:
            await route.abort()

    async def response(self, response):
        pending = self.pending
        if not pending or response.request != pending["request"] or not pending.get("released"):
            return
        result = {
            "request_id": pending["id"],
            "status": response.status,
            "url": response.url,
            "verified": False,
            "business_verified": False,
            "test_fixture": self.test_fixture,
            "state": "SUBMITTED_UNVERIFIED",
        }
        # A read-only host grant can return a login redirect. Verify transport,
        # not login or business success; never extend this rule to POST redirects.
        read_redirect = (
            pending.get("grant_read_host")
            and response.request.method == "GET"
            and 300 <= response.status < 400
        )
        if pending.get("transport_only") and (200 <= response.status < 300 or read_redirect):
            result.update(verified=True, provider_receipt="http:" + pending["digest"], state="HTTP_ACCEPTED")
        try:
            if int(response.headers.get("content-length", "0")) > 1000000:
                raise ValueError()
            value = await response.json()
            receipt = receipt_id(value)
            if (
                receipt
                and 200 <= response.status < 300
                and urlsplit(self.page.url).hostname
                in (
                    urlsplit(response.url).hostname,
                    urlsplit(pending.get("before", {}).get("url", "")).hostname,
                )
            ):
                # Receipt in a response AND newly visible confirmation text. A model
                # or HTTP 200 alone is never accepted as a business receipt.
                await self.page.get_by_text(receipt, exact=False).first.wait_for(timeout=4000)
                text = await self.page.locator("body").inner_text(timeout=2000)
                if re.search(r"订单|发布|预订|order|published|reservation", text, re.I):
                    result.update(
                        verified=True, business_verified=True, provider_receipt=receipt, state="SUCCEEDED"
                    )
                    from adex_tools.browser.policy import publication_metadata

                    details = publication_metadata(pending, value, self.page.url, receipt)
                    if details.get("permalink") and not await self.admit(details["permalink"]):
                        details.pop("permalink", None)
                    result.update(details)

            elif 200 <= response.status < 300 and pending.get("transport_only"):
                # This verifies only transport for a reviewed intermediate request,
                # never publication/order/payment or the user's overall goal.
                result.update(
                    verified=True, provider_receipt="http:" + pending["digest"], state="HTTP_ACCEPTED"
                )
        except Exception:
            pass
        self.last_receipt = result

    async def start(self, body):
        from playwright.async_api import async_playwright

        self.test_fixture = bool(body.get("_test_fixture"))
        self.read_hosts = set(body.get("read_hosts") or [urlsplit(body["url"]).hostname])
        self.pinned = (
            {"example.com": "93.184.215.14"}
            if self.test_fixture
            else await asyncio.wait_for(
                asyncio.to_thread(resolve_public_hosts, admitted_hosts(body["url"])), 6
            )
        )
        if urlsplit(body["url"]).hostname not in self.pinned:
            raise ValueError("BROWSER_DNS_BLOCKED")
        self.proxy = await asyncio.start_server(BrowserEgress(self.pinned).handle, "127.0.0.1", 0, limit=8192)
        port = self.proxy.sockets[0].getsockname()[1]
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            chromium_sandbox=True,
            proxy={"server": f"http://127.0.0.1:{port}", "bypass": "<-loopback>"},
            args=[
                "--disable-background-networking",
                "--disable-quic",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            ],
        )
        self.context = await self.browser.new_context(
            storage_state=body.get("storage"),
            accept_downloads=False,
            service_workers="block",
            viewport={"width": 1100, "height": 780},
        )
        await self.context.route("**/*", self.intercept)
        await self.context.route_web_socket("**/*", lambda ws: ws.close())
        self.context.on("response", lambda response: asyncio.create_task(self.response(response)))
        self.page = await self.context.new_page()
        self.watch(self.page)
        self.cdp = await self.context.new_cdp_session(self.page)
        self.context.on("page", lambda page: asyncio.create_task(self.activate(page)))
        await self.page.goto(body["url"], wait_until="commit", timeout=12000)
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=2000)
        except Exception:
            pass
        return await self.observe()

    def watch(self, page):
        self.tabs.setdefault(str(uuid4()), page) if page not in self.tabs.values() else None

        def dialog_open(dialog):
            self.dialog = dialog
            self.dialog_id = str(uuid4())
            self.dialog_url = urlsplit(page.url)._replace(query="", fragment="").geturl()

        page.on("dialog", dialog_open)

    async def activate(self, page):
        if len(self.tabs) >= 6 and page not in self.tabs.values():
            await page.close()
            return
        self.watch(page)
        cdp = await self.context.new_cdp_session(page)
        self.page, self.cdp = page, cdp

    async def observe(self, screenshot=False):
        if self.page.is_closed():
            available = [page for page in self.context.pages if not page.is_closed()]
            if not available:
                raise ValueError("BROWSER_SESSION_LOST")
            await self.activate(available[-1])
        if self.dialog:
            return {
                **(
                    self.last_view
                    or {
                        "url": self.page.url,
                        "title": "网页需要确认",
                        "observation_id": "dialog",
                        "nodes": [],
                    }
                ),
                "mode": self.mode,
                "pending": None,
                "dialog": {
                    "id": self.dialog_id,
                    "type": self.dialog.type,
                    "message": self.safe(self.dialog.message),
                    "url": self.dialog_url,
                },
            }
        tree = (await self.cdp.send("Accessibility.getFullAXTree"))["nodes"]
        nodes, handles = [], {}
        for node in tree:
            if node.get("ignored"):
                continue
            role = node.get("role", {}).get("value", "")
            name = self.safe(node.get("name", {}).get("value", ""))[:400]
            properties = {p["name"]: p["value"].get("value") for p in node.get("properties", [])}
            protected = bool(properties.get("protected")) or bool(SECRET.search(name))
            backend = node.get("backendDOMNodeId")
            if (
                properties.get("editable")
                or role
                in (
                    "button",
                    "link",
                    "textbox",
                    "combobox",
                    "checkbox",
                    "radio",
                    "searchbox",
                    "spinbutton",
                    "slider",
                )
            ) and backend:
                described = (await self.cdp.send("DOM.describeNode", {"backendNodeId": backend, "depth": 0}))[
                    "node"
                ]
                attributes = described.get("attributes", [])
                attrs = dict(zip(attributes[::2], attributes[1::2]))
                name = (
                    name
                    or self.safe(
                        attrs.get("aria-label")
                        or attrs.get("placeholder")
                        or attrs.get("data-placeholder")
                        or ""
                    )[:400]
                )
                protected = (
                    protected
                    or bool(SECRET.search(name))
                    or attrs.get("type", "").lower() == "password"
                    or bool(SECRET.search(attrs.get("autocomplete", "")))
                )
                if properties.get("editable"):
                    role = "textbox"
                    name = name or "可编辑区域"
                handle = str(backend)
                handles[handle] = {"backend": backend, "role": role, "name": name, "protected": protected}
                current_value = node.get("value", {}).get("value", "")
                frame_origin = ""
                if role in ("textbox", "searchbox", "combobox"):
                    obj = (await self.cdp.send("DOM.resolveNode", {"backendNodeId": backend}))["object"][
                        "objectId"
                    ]
                    observed = await self.cdp.send(
                        "Runtime.callFunctionOn",
                        {
                            "objectId": obj,
                            "functionDeclaration": "function(secret){return {origin:this.ownerDocument.location.origin,value:secret?'':String(this.value ?? this.innerText ?? '').slice(0,16000)}}",
                            "arguments": [{"value": protected}],
                            "returnByValue": True,
                        },
                    )
                    observed = observed.get("result", {}).get("value", {})
                    frame_origin = observed.get("origin", "")
                    if not protected:
                        current_value = observed.get("value", current_value)
                nodes.append(
                    {
                        "id": handle,
                        "role": role,
                        "name": name,
                        "protected": protected,
                        "frame_origin": frame_origin,
                        "input_type": attrs.get("type", "text"),
                        "autocomplete": attrs.get("autocomplete", ""),
                        "value": "[REDACTED]" if protected else self.safe(current_value)[:5000],
                    }
                )
            elif role in ("StaticText", "heading") and name:
                nodes.append({"role": role, "name": name})
            if len(nodes) >= 250:
                break
        revision = hashlib.sha256(
            json.dumps({"nodes": nodes, "url": self.page.url}, sort_keys=True).encode()
        ).hexdigest()[:24]
        self.revision, self.handles = revision, handles
        pending = None
        if self.pending and not self.pending.get("released"):
            self.pending.setdefault("observation_id", revision)
            self.pending.setdefault(
                "before",
                {"url": urlsplit(self.page.url)._replace(query="", fragment="").geturl(), "nodes": nodes},
            )
            pending = {
                k: v
                for k, v in self.pending.items()
                if k
                in (
                    "id",
                    "digest",
                    "preview",
                    "gesture",
                    "transport_only",
                    "grant_read_host",
                    "observation_id",
                    "before",
                )
            }
        # Cross-origin login widgets often have no accessible nodes in the main
        # CDP tree. Offer their actual visible frame as a user-opened login page;
        # never invent fields or expose token-bearing frame URLs to the model.
        self.embedded_login = None
        for frame in self.page.frames:
            if frame == self.page.main_frame or not re.search(r"login|signin|sign-in|登录", frame.url, re.I):
                continue
            parsed_frame = urlsplit(frame.url)
            if parsed_frame.scheme != "https" or parsed_frame.username or parsed_frame.password:
                continue
            try:
                if not await (await frame.frame_element()).is_visible():
                    continue
            except Exception:
                continue
            self.embedded_login = {
                "id": hashlib.sha256(frame.url.encode()).hexdigest()[:24],
                "origin": f"https://{parsed_frame.netloc}",
                "url": frame.url,
            }
            break
        result = {
            "url": urlsplit(self.page.url)._replace(query="", fragment="").geturl(),
            "title": self.safe(await self.page.title()),
            "observation_id": revision,
            "nodes": nodes,
            "embedded_login": {k: v for k, v in self.embedded_login.items() if k != "url"}
            if self.embedded_login
            else None,
            "pending": pending,
            "receipt": self.last_receipt,
            "provider": "TEST_FIXTURE" if self.test_fixture else "chromium",
            "mode": self.mode,
            "read_hosts": sorted(self.read_hosts),
            "_storage": self.clean_storage(await self.context.storage_state()),
        }
        if screenshot:
            result["screenshot"] = base64.b64encode(
                await self.page.screenshot(type="jpeg", quality=65)
            ).decode()
        result["tabs"] = [
            {
                "id": key,
                "url": urlsplit(page.url)._replace(query="", fragment="").geturl(),
                "active": page == self.page,
            }
            for key, page in list(self.tabs.items())
            if not page.is_closed()
        ]
        self.last_view = {k: v for k, v in result.items() if k not in ("_storage", "screenshot")}
        return result

    def clean_storage(self, state):
        def contains_secret(value):
            return any(secret and secret in str(value) for secret in self.secret_values)

        state["cookies"] = [
            cookie for cookie in state.get("cookies", []) if not contains_secret(cookie.get("value", ""))
        ]
        for origin in state.get("origins", []):
            origin["localStorage"] = [
                item
                for item in origin.get("localStorage", [])
                if not re.search(r"password|passwd|验证码|密码", item.get("name", ""), re.I)
                and not contains_secret(item.get("value", ""))
            ]
        return state

    async def secure_login(self, body):
        from adex_tools.browser.login import login_form

        if not body.get("human") or self.mode != "HUMAN":
            raise ValueError("BROWSER_LOGIN_REQUIRES_HUMAN")
        current = await self.observe()
        form = login_form(current)
        if (
            not form
            or form["origin"] != body.get("origin")
            or form["observation_id"] != body.get("observation_id")
        ):
            raise ValueError("STALE_BROWSER_LOGIN_FORM")
        permitted = {field["id"]: field for field in form["fields"]}
        fields = body.get("fields", [])
        submit = body.get("submit_element_id")
        if (
            not fields
            or len(fields) > 6
            or len({f["element_id"] for f in fields}) != len(fields)
            or any(f["element_id"] not in permitted for f in fields)
            or submit not in {b["id"] for b in form["buttons"]}
        ):
            raise ValueError("BROWSER_LOGIN_FIELDS_INVALID")
        # Frame ownership comes from native CDP document metadata, not webpage
        # JavaScript getters which an untrusted frame could override.
        tree = (await self.cdp.send("DOM.getDocument", {"depth": -1, "pierce": True}))["root"]
        origins = {}
        stack = [(tree, "")]
        while stack:
            node, origin = stack.pop()
            if node.get("nodeType") == 9:
                parsed = urlsplit(node.get("documentURL", ""))
                origin = f"{parsed.scheme}://{parsed.netloc}"
            if node.get("backendNodeId"):
                origins[node["backendNodeId"]] = origin
            children = node.get("children", []) + node.get("shadowRoots", [])
            if node.get("contentDocument"):
                children.append(node["contentDocument"])
            stack.extend((child, origin) for child in children)
        for handle in [field["element_id"] for field in fields] + [submit]:
            if origins.get(self.handles[handle]["backend"]) != form["origin"]:
                raise ValueError("BROWSER_LOGIN_FRAME_ORIGIN_MISMATCH")
        self.human_authorized = True
        self.human_until = asyncio.get_running_loop().time() + 10
        # Validate all handles before typing; no secrets enter snapshots or effects.
        for field in fields:
            if f"{urlsplit(self.page.url).scheme}://{urlsplit(self.page.url).netloc}" != form["origin"]:
                raise ValueError("STALE_BROWSER_LOGIN_FORM")
            value = field["text"]
            self.private_values.add(value)
            if permitted[field["element_id"]]["secret"]:
                self.secret_values.add(value)
            await self.cdp.send("DOM.focus", {"backendNodeId": self.handles[field["element_id"]]["backend"]})
            await self.page.keyboard.press("Meta+A" if sys.platform == "darwin" else "Control+A")
            await self.page.keyboard.insert_text(value)
        await self.cdp.send("DOM.scrollIntoViewIfNeeded", {"backendNodeId": self.handles[submit]["backend"]})
        box = (await self.cdp.send("DOM.getBoxModel", {"backendNodeId": self.handles[submit]["backend"]}))[
            "model"
        ]["content"]
        await self.page.mouse.click((box[0] + box[4]) / 2, (box[1] + box[5]) / 2)
        for _ in range(30):
            await asyncio.sleep(0.1)
            current = await self.observe()
            if not login_form(current):
                break
        return {**(await self.observe(True)), "login_submitted": True}

    async def operate(self, body):
        action = body["action"]
        human = body.get("human", False)
        if action == "open_login_frame":
            if not human or self.mode != "HUMAN":
                raise ValueError("BROWSER_LOGIN_REQUIRES_HUMAN")
            await self.observe()
            frame = self.embedded_login
            if not frame or body.get("frame_id") != frame["id"] or body.get("origin") != frame["origin"]:
                raise ValueError("STALE_BROWSER_LOGIN_FORM")
            if not await self.admit(frame["url"]):
                raise ValueError("BROWSER_URL_DENIED")
            self.human_authorized = True
            self.human_until = asyncio.get_running_loop().time() + 10
            try:
                await self.page.goto(frame["url"], wait_until="domcontentloaded", timeout=12000)
            except Exception:
                # Playwright errors can contain the full token-bearing iframe URL.
                raise ValueError("BROWSER_EMBEDDED_LOGIN_UNAVAILABLE") from None
            return await self.observe(True)
        if action == "secure_login":
            return await self.secure_login(body)
        if action in ("dialog_accept", "dialog_dismiss"):
            if (
                not human
                or self.mode != "HUMAN"
                or not self.dialog
                or body.get("dialog_id") != self.dialog_id
            ):
                raise ValueError("BROWSER_DIALOG_REQUIRES_HUMAN")
            dialog = self.dialog
            self.dialog = None
            self.dialog_id = None
            self.human_authorized = True
            self.human_until = asyncio.get_running_loop().time() + 10
            if action == "dialog_accept":
                await dialog.accept()
            else:
                await dialog.dismiss()
            return await self.observe(True)
        if action == "mode":
            if body["mode"] == "AGENT" and self.human_authorized:
                self.read_hosts.add(urlsplit(self.page.url).hostname)
            self.mode = body["mode"]
            self.human_authorized = self.mode == "HUMAN" and bool(body.get("human"))
            self.human_until = asyncio.get_running_loop().time() + 10 if self.human_authorized else 0
            return await self.observe(True)
        if action == "observe":
            return await self.observe(body.get("screenshot", False))
        if action in ("release", "validate_release"):
            pending = self.pending
            if (
                not pending
                or pending["id"] != body["request_id"]
                or pending["digest"] != body["digest"]
                or pending.get("released")
                or (body.get("allow", True) and pending["future"].done())
            ):
                raise ValueError("BROWSER_REQUEST_LOST")
            if body.get("allow", True):
                current = await self.observe()
                if current["observation_id"] != pending["observation_id"]:
                    raise ValueError("BROWSER_APPROVAL_SNAPSHOT_CHANGED")
            if action == "validate_release":
                return {"valid": True}
            pending["released"] = True
            if not pending["future"].done():
                pending["future"].set_result(bool(body["allow"]))
            if not body["allow"]:
                self.pending = None
                self.last_receipt = None
                return await self.observe(True)
            for _ in range(60):
                if self.last_receipt and self.last_receipt["request_id"] == pending["id"]:
                    break
                await asyncio.sleep(0.1)
            return await self.observe()
        if self.pending and not self.pending.get("released"):
            raise ValueError("BROWSER_APPROVAL_REQUIRED")
        if (self.mode == "HUMAN") != human:
            raise ValueError("BROWSER_CONTROL_MODE_CHANGED")
        if human and action != "observe":
            self.human_authorized = True
            self.human_until = asyncio.get_running_loop().time() + 10
        if action not in (
            "navigate",
            "click",
            "type",
            "select",
            "scroll",
            "back",
            "upload",
            "key",
            "point",
            "switch_tab",
        ):
            raise ValueError("BROWSER_ACTION_NOT_ALLOWED")
        if not human:
            await self.observe()
        if not human and body.get("observation_id") != self.revision:
            raise ValueError("STALE_BROWSER_OBSERVATION")
        if self.pending and self.pending.get("released"):
            if not self.last_receipt or not self.last_receipt.get("verified"):
                raise ValueError("PROVIDER_UNKNOWN")
            self.pending = None
        self.critical = False
        self.gesture = ""
        target = self.handles.get(body.get("element_id", ""))
        if action in ("click", "type", "select", "upload") and not (
            human and action == "type" and not body.get("element_id")
        ):
            if not target:
                raise ValueError("STALE_BROWSER_ELEMENT")
            if target["protected"] and not human:
                raise ValueError("BROWSER_LOGIN_REQUIRED")
            self.gesture = target["name"]
            self.critical = bool(CRITICAL.search(self.gesture))
        if human and action == "type":
            self.private_values.add(body.get("text", ""))
            if target and target.get("protected"):
                self.secret_values.add(body.get("text", ""))

        async def perform():
            if action == "switch_tab":
                page = self.tabs.get(body.get("element_id"))
                if page is None or page.is_closed():
                    raise ValueError("BROWSER_TAB_NOT_FOUND")
                await self.activate(page)
            elif action == "navigate":
                if not await self.admit(body["url"]):
                    raise ValueError("BROWSER_URL_NOT_ALLOWED")
                await self.page.goto(body["url"], wait_until="commit", timeout=10000)
            elif action == "back":
                await self.page.go_back(wait_until="commit", timeout=10000)
            elif action == "scroll":
                await self.page.mouse.wheel(0, -500 if body.get("text") == "up" else 500)
            elif action == "type" and human and not body.get("element_id"):
                await self.page.keyboard.insert_text(body.get("text", ""))
            elif action == "key" and human:
                if body.get("text") not in ("Enter", "Tab", "Backspace", "Escape", "ArrowDown", "ArrowUp"):
                    raise ValueError("BROWSER_KEY_NOT_ALLOWED")
                await self.page.keyboard.press(body["text"])
            elif action == "point" and human:
                await self.page.mouse.click(max(0, min(1099, body["x"])), max(0, min(779, body["y"])))
            elif action in ("click", "type", "select", "upload"):
                backend = target["backend"]
                await self.cdp.send("DOM.scrollIntoViewIfNeeded", {"backendNodeId": backend})
                if action in ("type", "select"):
                    await self.cdp.send("DOM.focus", {"backendNodeId": backend})
                    await self.page.keyboard.press("Meta+A" if sys.platform == "darwin" else "Control+A")
                    await self.page.keyboard.insert_text(body.get("text", ""))
                    if action == "select":
                        await self.page.keyboard.press("Enter")
                elif action == "click":
                    box = (await self.cdp.send("DOM.getBoxModel", {"backendNodeId": backend}))["model"][
                        "content"
                    ]
                    await self.page.mouse.click((box[0] + box[4]) / 2, (box[1] + box[5]) / 2)
                else:
                    obj = (await self.cdp.send("DOM.resolveNode", {"backendNodeId": backend}))["object"][
                        "objectId"
                    ]
                    # Fixed trusted implementation, never code supplied by a model.
                    await self.cdp.send(
                        "Runtime.callFunctionOn",
                        {
                            "objectId": obj,
                            "functionDeclaration": """function(b64,name,mime){const bytes=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));const d=new DataTransfer();d.items.add(new File([bytes],name,{type:mime}));this.files=d.files;this.dispatchEvent(new Event('change',{bubbles:true}));}""",
                            "arguments": [
                                {"value": body["file_base64"]},
                                {"value": body["file_name"]},
                                {"value": body["file_mime"]},
                            ],
                        },
                    )

        task = asyncio.create_task(perform())
        try:
            await asyncio.wait_for(asyncio.shield(task), 2)
        except TimeoutError:
            if not self.pending:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        return await self.observe(human)


async def main():
    broker = Broker()
    first = True
    while raw := await asyncio.to_thread(sys.stdin.buffer.readline, 8 * 1024 * 1024):
        try:
            body = json.loads(raw)
            if body.get("action") == "close":
                break
            result = await broker.start(body) if first else await broker.operate(body)
            first = False
        except Exception as error:
            code = str(error)
            result = {"error": code if re.fullmatch("[A-Z_]{3,80}", code) else "BROWSER_OPERATION_FAILED"}
        print(json.dumps(result, ensure_ascii=False), flush=True)
    if hasattr(broker, "browser"):
        await broker.browser.close()
        await broker.playwright.stop()
        broker.proxy.close()


if __name__ == "__main__":
    asyncio.run(main())
