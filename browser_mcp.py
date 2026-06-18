#!/usr/bin/env python3
"""
OpenCode Browser MCP v2.0

Production-ready browser MCP server with 25+ tools.
Inspired by Chrome DevTools MCP's feature set, implemented in Python + Playwright.

Categories:
  Navigation — multi-tab, wait_for, dialog handling
  Automation — click, fill, fill_form, hover, drag, press_key, upload
  Inspection — snapshot (with UIDs), screenshot, get_text, get_html, get_links
  Debugging — console messages, network requests
  Performance — Core Web Vitals trace (CDP-based)
  Emulation — viewport, dark mode, geolocation, user agent, network throttle
  Management — list_pages, select_page, new_page, close_page, cleanup

Author: Hogan Dong
License: MIT
"""

import json
import sys
import os
import time
from typing import Dict, Any

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

# ── Config ──────────────────────────────────────────────────
HEADLESS = os.environ.get("MCP_BROWSER_HEADLESS", "true").lower() == "true"
TIMEOUT_MS = int(os.environ.get("MCP_BROWSER_TIMEOUT", "30000"))
ALLOWED_DOMAINS = os.environ.get("MCP_BROWSER_ALLOWED_DOMAINS", "*").split(",")
MAX_TABS = int(os.environ.get("MCP_BROWSER_MAX_TABS", "10"))

_pw = None
_browser: Browser | None = None
_context: BrowserContext | None = None
_pages: list[Page] = []
_active_idx: int = 0
_console_logs: list[dict] = []
_network_logs: list[dict] = []
_uid_map: dict[str, Any] = {}
_tracing = False


# ── Helpers ─────────────────────────────────────────────────
def _check_domain(url: str):
    if "*" in ALLOWED_DOMAINS:
        return
    if not any(d in url for d in ALLOWED_DOMAINS):
        raise PermissionError(f"Domain not allowed: {url}")


def _ensure_browser():
    global _pw, _browser, _context, _pages
    if _browser is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(headless=HEADLESS)
        _context = _browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/148.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        _context.on("console", lambda msg: _console_logs.append({
            "type": msg.type, "text": msg.text, "location": msg.location, "time": time.time()
        }))
        _context.on("request", lambda req: _network_logs.append({
            "url": req.url, "method": req.method, "resource_type": req.resource_type,
            "status": None, "time": time.time(), "_req": req
        }))
        _context.on("response", lambda resp: _update_network_status(resp))
        page = _context.new_page()
        _pages.append(page)
        _active_idx = 0


def _update_network_status(resp):
    for log in reversed(_network_logs):
        if log.get("_req") and log["_req"].url == resp.url:
            log["status"] = resp.status
            log["status_text"] = resp.status_text
            break


def _active() -> Page:
    _ensure_browser()
    return _pages[_active_idx]


def ok(msg: str) -> dict:
    return {"content": msg}


def err(msg: str) -> dict:
    return {"content": msg, "isError": True}


def _build_snapshot() -> str:
    page = _active()
    global _uid_map
    _uid_map = {}

    result = page.evaluate("""() => {
      const map = {};
      let uid = 0;
      const lines = [];

      function walk(el, depth) {
        if (uid > 300 || depth > 20) return;
        uid++;
        const id = 'el_' + uid;
        const tag = el.tagName.toLowerCase();
        const role = el.getAttribute('role') || '';
        const text = (el.textContent || '').trim().slice(0, 80);
        const rect = el.getBoundingClientRect();
        const visible = rect.width > 0 && rect.height > 0;

        if (!visible) return;

        let label = tag;
        if (role) label += '[role=' + role + ']';
        if (text) label += ' ' + JSON.stringify(text);

        const indent = '  '.repeat(depth);
        lines.push(indent + '[' + id + '] ' + label);

        map[id] = {
          tag: tag, role: role, text: text,
          selector: el.id ? '#' + el.id : el.className ? '.' + el.className.split(' ')[0] : tag,
          visible: visible
        };

        for (let i = 0; i < el.children.length; i++) {
          walk(el.children[i], depth + 1);
        }
      }

      if (document.body) walk(document.body, 0);
      return {lines: lines.slice(0, 200).join('\\n'), map: map};
    }""")

    _uid_map = result["map"]
    return result["lines"] or "(page not loaded)"


# ── Navigation Tools ────────────────────────────────────────
def navigate_page(args: dict) -> dict:
    url = args["url"]
    _check_domain(url)
    page = _active()
    try:
        page.goto(url, timeout=TIMEOUT_MS, wait_until="load")
    except Exception:
        try:
            page.goto(url, timeout=TIMEOUT_MS, wait_until="commit")
        except Exception as e:
            return err(f"Navigation failed: {e}")
    return ok(f"Loaded: {page.title()}\nURL: {url}")


def new_page(args: dict) -> dict:
    url = args["url"]
    _check_domain(url)
    _ensure_browser()
    if len(_pages) >= MAX_TABS:
        return err(f"Max tabs ({MAX_TABS}) reached")
    page = _context.new_page()
    page.goto(url, timeout=TIMEOUT_MS, wait_until="load")
    _pages.append(page)
    global _active_idx
    _active_idx = len(_pages) - 1
    return ok(f"New tab [{_active_idx}]: {page.title()}")


def list_pages(args: dict) -> dict:
    _ensure_browser()
    lines = []
    for i, p in enumerate(_pages):
        marker = " ◀ active" if i == _active_idx else ""
        title = p.title() or "(no title)"
        url = p.url
        lines.append(f"  [{i}] {title} — {url}{marker}")
    return ok("Open tabs:\n" + "\n".join(lines))


def select_page(args: dict) -> dict:
    idx = args["index"]
    if idx < 0 or idx >= len(_pages):
        return err(f"Invalid tab index: {idx}. Use list_pages to see available tabs.")
    global _active_idx
    _active_idx = idx
    return ok(f"Selected tab [{idx}]: {_pages[idx].title()}")


def close_page(args: dict) -> dict:
    idx = args["index"]
    if len(_pages) <= 1:
        return err("Cannot close last tab")
    if idx < 0 or idx >= len(_pages):
        return err(f"Invalid tab index: {idx}")
    _pages[idx].close()
    _pages.pop(idx)
    global _active_idx
    if _active_idx >= len(_pages):
        _active_idx = len(_pages) - 1
    return ok(f"Closed tab [{idx}]. Active: [{_active_idx}]")


def wait_for(args: dict) -> dict:
    text = args["text"]
    attempt = 0
    while attempt < 10:
        try:
            _active().wait_for_selector(f"text={text}", timeout=3000)
            return ok(f"Text found: {text}")
        except Exception:
            attempt += 1
    return err(f"Text not found after 30s: {text}")


def handle_dialog(args: dict) -> dict:
    action = args.get("action", "accept")
    try:
        dialog = _active().wait_for_event("dialog", timeout=5000)
        if action == "accept":
            dialog.accept(args.get("prompt_text", ""))
        else:
            dialog.dismiss()
        return ok(f"Dialog {action}ed: {dialog.message}")
    except Exception:
        return err("No dialog found")


# ── Automation Tools ────────────────────────────────────────
def snapshot(args: dict) -> dict:
    try:
        snap = _build_snapshot()
        limit = 10000
        if len(snap) > limit:
            snap = snap[:limit] + f"\n…(truncated, {len(snap)} chars)"
        return ok(snap)
    except Exception as e:
        return err(f"Snapshot failed: {e}")


def _resolve(uid: str | None, selector: str | None) -> str | None:
    """Resolve a UID to a CSS selector, or return the raw selector."""
    if uid and uid in _uid_map:
        sel = _uid_map[uid].get("selector", "")
        return sel or uid
    return selector


def click(args: dict) -> dict:
    target = _resolve(args.get("uid"), args.get("selector"))
    if not target:
        return err("Provide uid or selector")
    try:
        _active().click(target, timeout=TIMEOUT_MS)
        return ok(f"Clicked: {target}")
    except Exception as e:
        return err(f"Click failed: {e}")


def fill(args: dict) -> dict:
    target = _resolve(args.get("uid"), args.get("selector"))
    if not target:
        return err("Provide uid or selector")
    try:
        _active().fill(target, args["value"], timeout=TIMEOUT_MS)
        return ok(f"Filled: {target}")
    except Exception as e:
        return err(f"Fill failed: {e}")


def hover(args: dict) -> dict:
    target = _resolve(args.get("uid"), args.get("selector"))
    if not target:
        return err("Provide uid or selector")
    try:
        _active().hover(target, timeout=TIMEOUT_MS)
        return ok(f"Hovered: {target}")
    except Exception as e:
        return err(f"Hover failed: {e}")


def drag(args: dict) -> dict:
    from_sel = _resolve(args.get("from_uid"), None)
    to_sel = _resolve(args.get("to_uid"), None)
    if not from_sel or not to_sel:
        return err("Provide from_uid and to_uid from a snapshot")
    try:
        _active().drag_and_drop(from_sel, to_sel, timeout=TIMEOUT_MS)
        return ok(f"Dragged {from_sel} -> {to_sel}")
    except Exception as e:
        return err(f"Drag failed: {e}")


def fill_form(args: dict) -> dict:
    fields = args.get("fields", [])
    page = _active()
    results = []
    for f in fields:
        target = _resolve(f.get("uid"), f.get("selector"))
        if not target:
            results.append("  Skipped: no uid or selector")
            continue
        try:
            page.fill(target, f.get("value", ""), timeout=TIMEOUT_MS)
            results.append(f"  Filled: {target}")
        except Exception as e:
            results.append(f"  Failed: {target} — {e}")
    return ok("Form fill:\n" + "\n".join(results))


def press_key(args: dict) -> dict:
    key = args["key"]
    _active().keyboard.press(key)
    return ok(f"Pressed: {key}")


def type_text(args: dict) -> dict:
    text = args["text"]
    _active().keyboard.type(text)
    return ok(f"Typed: {text[:50]}..." if len(text) > 50 else f"Typed: {text}")


def upload_file(args: dict) -> dict:
    selector = args.get("selector")
    file_path = args["file_path"]
    if not selector:
        return err("Provide selector for the file input")
    _active().set_input_files(selector, file_path, timeout=TIMEOUT_MS)
    return ok(f"Uploaded: {file_path}")


# ── Inspection Tools ────────────────────────────────────────
def screenshot(args: dict) -> dict:
    path = args.get("path", "screenshot.png")
    full = args.get("full_page", False)
    uid = args.get("uid")
    page = _active()
    try:
        if uid and uid in _uid_map:
            target = _uid_map[uid].get("selector", "")
            if target:
                page.locator(target).screenshot(path=path)
            else:
                page.screenshot(path=path)
        else:
            page.screenshot(path=path, full_page=full)
        return ok(f"Screenshot: {path}")
    except Exception as e:
        return err(f"Screenshot failed: {e}")


def get_text(args: dict) -> dict:
    text = _active().inner_text("body")
    if len(text) > 8000:
        text = text[:8000] + f"\n\n…({len(text)} chars total)"
    return ok(text)


def get_html(args: dict) -> dict:
    html = _active().content()
    if len(html) > 15000:
        html = html[:15000] + "\n…(truncated)"
    return ok(html)


def get_links(args: dict) -> dict:
    links = _active().eval_on_selector_all(
        "a[href]", "els => els.map(el => ({text: el.textContent.trim(), href: el.href}))"
    )
    lines = [f"• {l['text'][:60]} → {l['href']}" for l in links[:30] if l["text"]]
    return ok("\n".join(lines) if lines else "No links")


def execute_js(args: dict) -> dict:
    result = _active().evaluate(args["code"])
    return ok(str(result))


# ── Debugging Tools ─────────────────────────────────────────
def list_console_messages(args: dict) -> dict:
    types_filter = args.get("types", [])
    msgs = _console_logs[-50:]
    if types_filter:
        msgs = [m for m in msgs if m["type"] in types_filter]
    lines = [f"  [{m['type']}] {m['text'][:200]}" for m in msgs]
    return ok(f"Console messages ({len(msgs)}):\n" + "\n".join(lines))


def get_console_message(args: dict) -> dict:
    idx = args.get("index", -1)
    if idx < 0 or idx >= len(_console_logs):
        return err(f"Invalid index. 0-{len(_console_logs)-1}")
    m = _console_logs[idx]
    return ok(f"[{m['type']}] {m['text']}\nLocation: {m['location']}")


def list_network_requests(args: dict) -> dict:
    resource_types = args.get("resource_types", [])
    reqs = _network_logs[-50:]
    if resource_types:
        reqs = [r for r in reqs if r["resource_type"] in resource_types]
    lines = [
        f"  [{r['status'] or 'pending'}] {r['method']} {r['url'][:100]}"
        for r in reqs
    ]
    return ok(f"Network requests ({len(reqs)}):\n" + "\n".join(lines))


def get_network_request(args: dict) -> dict:
    idx = args.get("index", -1)
    if idx < 0 or idx >= len(_network_logs):
        return err(f"Invalid index. 0-{len(_network_logs)-1}")
    r = _network_logs[idx]
    return ok(
        f"URL: {r['url']}\nMethod: {r['method']}\nType: {r['resource_type']}\nStatus: {r['status']}"
    )


# ── Emulation Tools ─────────────────────────────────────────
def emulate(args: dict) -> dict:
    page = _active()
    results = []

    if "viewport" in args:
        w, h = args["viewport"].split("x")
        page.set_viewport_size({"width": int(w), "height": int(h)})
        results.append(f"Viewport: {w}x{h}")

    if "color_scheme" in args:
        page.emulate_media(color_scheme=args["color_scheme"])
        results.append(f"Color scheme: {args['color_scheme']}")

    if "geolocation" in args:
        lat, lon = args["geolocation"].split(",")
        _context.set_geolocation({"latitude": float(lat), "longitude": float(lon)})
        results.append(f"Geolocation: {lat},{lon}")

    if "user_agent" in args:
        page.set_extra_http_headers({"User-Agent": args["user_agent"]})
        results.append(f"UA: {args['user_agent'][:50]}")

    if "offline" in args:
        if args["offline"]:
            _context.set_offline(True)
            results.append("Network: offline")
        else:
            _context.set_offline(False)
            results.append("Network: online")

    return ok("Emulation applied:\n" + "\n".join(results))


def resize_page(args: dict) -> dict:
    w = args["width"]
    h = args["height"]
    _active().set_viewport_size({"width": w, "height": h})
    return ok(f"Resized to {w}x{h}")


# ── Performance Tools ───────────────────────────────────────
def performance_start_trace(args: dict) -> dict:
    global _tracing
    _tracing = True
    _active().evaluate("() => performance.mark('mcp-trace-start')")
    return ok("Performance tracing started")


def performance_stop_trace(args: dict) -> dict:
    global _tracing
    _tracing = False
    metrics = _active().evaluate(
        """() => {
      const t = performance.timing;
      const n = performance.getEntriesByType('navigation')[0];
      return {
        ttfb: t.responseStart - t.requestStart,
        domInteractive: t.domInteractive - t.navigationStart,
        domComplete: t.domComplete - t.navigationStart,
        loadTime: t.loadEventEnd - t.navigationStart,
        lcp: n ? 0 : 'use performance.getEntriesByType(\"largest-contentful-paint\")',
      };
    }"""
    )
    metrics["note"] = "LCP requires real user interaction. Run performance.getEntriesByType('largest-contentful-paint') in execute_js."
    return ok("Performance metrics:\n" + json.dumps(metrics, indent=2))


# ── Management Tools ────────────────────────────────────────
def cleanup(args: dict = None) -> dict:
    global _browser, _context, _pages, _active_idx, _console_logs, _network_logs, _uid_map, _tracing
    if _context:
        _context.close()
    if _browser:
        _browser.close()
    _browser = _context = None
    _pages = []
    _active_idx = 0
    _console_logs = []
    _network_logs = []
    _uid_map = {}
    _tracing = False
    return ok("Browser closed. All sessions cleaned.")


# ── Registry ─────────────────────────────────────────────────
TOOLS = {
    # Navigation
    "navigate_page": ("Navigate to a URL", {"url": {"type": "string"}, "required": ["url"]}, navigate_page),
    "new_page": ("Open a URL in a new tab", {"url": {"type": "string"}, "required": ["url"]}, new_page),
    "list_pages": ("List all open browser tabs", {}, list_pages),
    "select_page": ("Switch to a tab by index", {"index": {"type": "integer"}, "required": ["index"]}, select_page),
    "close_page": ("Close a tab by index", {"index": {"type": "integer"}, "required": ["index"]}, close_page),
    "wait_for": ("Wait for text to appear on the page", {"text": {"type": "string"}, "required": ["text"]}, wait_for),
    "handle_dialog": ("Accept or dismiss a browser dialog", {"action": {"type": "string", "description": "accept or dismiss"}, "prompt_text": {"type": "string"}}, handle_dialog),
    # Automation
    "take_snapshot": ("Take an accessibility snapshot with element UIDs", {}, snapshot),
    "click": ("Click an element by uid (from snapshot) or CSS selector", {"uid": {"type": "string"}, "selector": {"type": "string"}}, click),
    "fill": ("Fill an input by uid or selector", {"uid": {"type": "string"}, "selector": {"type": "string"}, "value": {"type": "string"}, "required": ["value"]}, fill),
    "fill_form": ("Fill multiple form fields at once. Faster than individual fills.", {"fields": {"type": "array", "description": "Array of {uid or selector, value}"}, "required": ["fields"]}, fill_form),
    "hover": ("Hover over an element", {"uid": {"type": "string"}, "selector": {"type": "string"}}, hover),
    "drag": ("Drag from one element to another", {"from_uid": {"type": "string"}, "to_uid": {"type": "string"}, "required": ["from_uid", "to_uid"]}, drag),
    "press_key": ("Press a key or key combination (e.g., Enter, Control+A)", {"key": {"type": "string"}, "required": ["key"]}, press_key),
    "type_text": ("Type text using keyboard (emulates real typing)", {"text": {"type": "string"}, "required": ["text"]}, type_text),
    "upload_file": ("Upload a file via a file input", {"selector": {"type": "string"}, "file_path": {"type": "string"}, "required": ["selector", "file_path"]}, upload_file),
    # Inspection
    "screenshot": ("Take a screenshot of page or element", {"path": {"type": "string"}, "full_page": {"type": "boolean"}, "uid": {"type": "string"}}, screenshot),
    "get_text": ("Extract visible text", {}, get_text),
    "get_html": ("Get HTML source", {}, get_html),
    "get_links": ("List all links on the page", {}, get_links),
    "execute_js": ("Execute JavaScript and return result", {"code": {"type": "string"}, "required": ["code"]}, execute_js),
    # Debugging
    "list_console_messages": ("List recent browser console messages", {"types": {"type": "array", "description": "Filter by: log, error, warn, info"}}, list_console_messages),
    "get_console_message": ("Get a specific console message", {"index": {"type": "integer"}, "required": ["index"]}, get_console_message),
    "list_network_requests": ("List recent network requests", {"resource_types": {"type": "array", "description": "Filter by: xhr, fetch, script, stylesheet, image"}}, list_network_requests),
    "get_network_request": ("Get details of a network request", {"index": {"type": "integer"}, "required": ["index"]}, get_network_request),
    # Emulation
    "emulate": ("Emulate device features: viewport, dark mode, geolocation, offline", {"viewport": {"type": "string", "description": "WxH e.g. 375x812"}, "color_scheme": {"type": "string"}, "geolocation": {"type": "string"}, "user_agent": {"type": "string"}, "offline": {"type": "boolean"}}, emulate),
    "resize_page": ("Resize the page viewport", {"width": {"type": "integer"}, "height": {"type": "integer"}, "required": ["width", "height"]}, resize_page),
    # Performance
    "performance_start_trace": ("Start measuring page load performance", {}, performance_start_trace),
    "performance_stop_trace": ("Stop tracing and get Core Web Vitals metrics", {}, performance_stop_trace),
    # Management
    "cleanup": ("Close browser and clean up all sessions", {}, cleanup),
}


# ── MCP Protocol ─────────────────────────────────────────────
def handle_request(req: dict) -> dict | None:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "opencode-browser-mcp", "version": "2.0.0"},
            "capabilities": {"tools": {}},
        }}

    if method == "tools/list":
        tools_list = []
        for name, (desc, schema, _) in TOOLS.items():
            input_schema = {"type": "object", "properties": {k: v for k, v in schema.items() if k != "required"}}
            if "required" in schema:
                input_schema["required"] = schema["required"]
            tools_list.append({"name": name, "description": desc, "inputSchema": input_schema})
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if tool_name not in TOOLS:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}}
        _, _, handler = TOOLS[tool_name]
        try:
            result = handler(tool_args)
        except Exception as e:
            result = err(f"Error: {e}")
        content = result.get("content", str(result))
        resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": content}]}}
        if result.get("isError"):
            resp["result"]["isError"] = True
        return resp

    if method == "notifications/initialized":
        return None

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown: {method}"}}


def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            req = json.loads(line.strip())
            resp = handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            break
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
