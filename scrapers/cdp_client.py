"""Chrome DevTools Protocol 同步客户端（连接已登录的美团 Chrome）。"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

try:
    import websocket
except ImportError as exc:  # pragma: no cover
    raise SystemExit("请先安装 websocket-client: pip install websocket-client") from exc


class CDPError(RuntimeError):
    pass


@dataclass
class CapturedResponse:
    url: str
    status: int
    body: str
    mime_type: str = ""


@dataclass
class CDPSession:
    ws_url: str
    _ws: Any = field(init=False, repr=False)
    _msg_id: int = field(default=0, init=False)
    _events: list[dict] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._ws = websocket.create_connection(self.ws_url, timeout=60)
        self._ws.settimeout(60)

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass

    def call(self, method: str, params: Optional[dict] = None, timeout: float = 60) -> dict:
        self._msg_id += 1
        mid = self._msg_id
        self._ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self._ws.recv()
            data = json.loads(raw)
            if data.get("id") == mid:
                if "error" in data:
                    raise CDPError(f"{method}: {data['error']}")
                return data.get("result", {})
            if "method" in data:
                self._events.append(data)
        raise CDPError(f"{method} 超时")

    def drain_events(self) -> list[dict]:
        events, self._events = self._events, []
        return events

    def enable_network(self) -> None:
        self.call("Network.enable", {"maxTotalBufferSize": 50_000_000, "maxResourceBufferSize": 10_000_000})
        self.call("Page.enable")

    def navigate(self, url: str, wait_sec: float = 3.0) -> None:
        self.call("Page.navigate", {"url": url})
        time.sleep(wait_sec)

    def wait_ready(self, timeout: float = 90) -> None:
        deadline = time.time() + timeout
        last_err = None
        while time.time() < deadline:
            try:
                state = self.evaluate("document.readyState", await_promise=False)
                if state in ("interactive", "complete"):
                    time.sleep(1.5)
                    return
            except Exception as exc:  # noqa: BLE001
                last_err = exc
            time.sleep(1)
        raise CDPError(f"wait_ready 超时: {last_err}")

    def reload(self, wait_sec: float = 4.0) -> None:
        self.call("Page.reload", {"ignoreCache": True})
        time.sleep(wait_sec)

    def evaluate(self, expression: str, await_promise: bool = True) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
            },
        )
        if result.get("exceptionDetails"):
            raise CDPError(str(result["exceptionDetails"]))
        val = result.get("result", {})
        if val.get("type") == "undefined":
            return None
        return val.get("value")

    def fetch_json_in_page(self, url: str) -> Any:
        expr = f"""
(async () => {{
  const r = await fetch({json.dumps(url)}, {{
    credentials: 'include',
    headers: {{ 'Accept': 'application/json, text/plain, */*' }}
  }});
  const text = await r.text();
  try {{
    return {{ ok: r.ok, status: r.status, url: r.url, data: JSON.parse(text) }};
  }} catch (e) {{
    return {{ ok: r.ok, status: r.status, url: r.url, text: text.slice(0, 4000) }};
  }}
}})()
"""
        return self.evaluate(expr)

    def scrape_dom_tables(self) -> list[dict]:
        js = """
(() => {
  const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
  const tables = [...document.querySelectorAll('table')];
  return tables.map((t) => {
    const headers = [...t.querySelectorAll('thead th')].map((x) => norm(x.innerText));
    let rows = [...t.querySelectorAll('tbody tr')].map((tr) =>
      [...tr.querySelectorAll('td')].map((td) => norm(td.innerText))
    );
    if (!headers.length && rows.length) {
      return { headers: rows[0] || [], rows: rows.slice(1) };
    }
    return { headers, rows };
  }).filter((t) => t.rows && t.rows.length);
})()
"""
        data = self.evaluate(js, await_promise=False)
        return data if isinstance(data, list) else []

    def capture_responses(
        self,
        url_filter: Callable[[str], bool],
        duration_sec: float = 15.0,
        reload: bool = False,
    ) -> list[CapturedResponse]:
        self.enable_network()
        pending: dict[str, str] = {}
        captured: list[CapturedResponse] = []
        if reload:
            self.call("Page.reload", {"ignoreCache": True})
        deadline = time.time() + duration_sec
        while time.time() < deadline:
            for evt in self.drain_events():
                method = evt.get("method")
                params = evt.get("params", {})
                if method == "Network.responseReceived":
                    resp = params.get("response", {})
                    req_id = params.get("requestId")
                    url = resp.get("url", "")
                    mime = resp.get("mimeType", "")
                    if req_id and url_filter(url):
                        pending[req_id] = url
                elif method == "Network.loadingFinished":
                    req_id = params.get("requestId")
                    if req_id in pending:
                        url = pending.pop(req_id)
                        try:
                            body = self.call("Network.getResponseBody", {"requestId": req_id})
                            text = body.get("body", "")
                            if body.get("base64Encoded"):
                                import base64

                                text = base64.b64decode(text).decode("utf-8", errors="replace")
                            captured.append(CapturedResponse(url=url, status=200, body=text, mime_type=""))
                        except CDPError:
                            pass
            time.sleep(0.15)
        return captured


def list_tabs(port: int = 9222) -> list[dict]:
    url = f"http://127.0.0.1:{port}/json/list"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ConnectionRefusedError) as exc:
        raise CDPError(
            f"无法连接 Chrome 调试端口 {port}。请先运行: bash scripts/start_chrome_meituan.sh"
        ) from exc


def pick_tab(port: int, patterns: list[str]) -> dict:
    tabs = list_tabs(port)
    for tab in tabs:
        u = tab.get("url", "")
        if any(p in u for p in patterns) and tab.get("webSocketDebuggerUrl"):
            return tab
    for tab in tabs:
        if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
            return tab
    raise CDPError(
        f"未找到可用 Chrome 标签页（端口 {port}）。请先运行 scripts/start_chrome_meituan.sh 并登录美团后台。"
    )


def connect_tab(port: int = 9222, patterns: Optional[list[str]] = None) -> CDPSession:
    patterns = patterns or ["igate.waimai.meituan.com", "meituan.com", "sankuai.com"]
    tab = pick_tab(port, patterns)
    return CDPSession(tab["webSocketDebuggerUrl"])
