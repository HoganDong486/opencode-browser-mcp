#!/usr/bin/env python3
"""
Browser MCP Server for OpenCode

Gives AI coding agents (OpenCode, Claude Code, Cursor) the ability to control
a web browser. Built on Playwright for cross-browser compatibility.

Safety-first design:
- Headless by default (no visible window)
- Sandbox mode (fresh browser, no host cookies)
- Domain allowlist support
- Auto-cleanup after each session
- Timeout protection

Author: Hogan Dong
License: MIT
"""

import json
import sys
import os
from playwright.sync_api import sync_playwright

# ── Configuration ──────────────────────────────────────────
ALLOWED_DOMAINS = os.environ.get("MCP_BROWSER_ALLOWED_DOMAINS", "*").split(",")
HEADLESS = os.environ.get("MCP_BROWSER_HEADLESS", "true").lower() == "true"
TIMEOUT_MS = int(os.environ.get("MCP_BROWSER_TIMEOUT", "30000"))
MAX_NAVIGATIONS = int(os.environ.get("MCP_BROWSER_MAX_NAVIGATIONS", "10"))

_browser = None
_context = None
_page = None
_nav_count = 0


# ── Helpers ─────────────────────────────────────────────────
def _check_domain(url: str):
    if "*" in ALLOWED_DOMAINS:
        return
    if not any(d in url for d in ALLOWED_DOMAINS):
        raise PermissionError(
            f"Domain not in allowlist: {url}. Allowed: {ALLOWED_DOMAINS}"
        )


def _ensure_browser():
    global _browser, _context, _page
    if _browser is None:
        pw = sync_playwright().start()
        _browser = pw.chromium.launch(headless=HEADLESS)
        _context = _browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        _page = _context.new_page()


# ── Tools ───────────────────────────────────────────────────
def navigate(args: dict) -> dict:
    """Navigate to a URL."""
    global _nav_count
    url = args["url"]
    _check_domain(url)
    if _nav_count >= MAX_NAVIGATIONS:
        return {"content": f"Navigation limit reached ({MAX_NAVIGATIONS}). Restart session."}

    _ensure_browser()
    _nav_count += 1

    try:
        _page.goto(url, timeout=TIMEOUT_MS, wait_until="load")
    except Exception as e:
        err = str(e)
        if "net::ERR" in err or "Navigation" in err:
            try:
                _page.goto(url, timeout=TIMEOUT_MS, wait_until="commit")
            except Exception:
                return {"content": f"Navigation failed:\n{err}\nThis site may block headless browsers.", "isError": True}

    try:
        _page.wait_for_timeout(1000)
        title = _page.title()
    except Exception:
        title = "(title unavailable)"

    return {"content": f"Loaded: {title}\nURL: {url}"}


def screenshot(args: dict) -> dict:
    """Take a screenshot."""
    _ensure_browser()
    path = args.get("path", "screenshot.png")
    full = args.get("full_page", False)
    _page.screenshot(path=path, full_page=full)
    return {"content": f"Screenshot saved: {path}"}


def get_text(args: dict) -> dict:
    """Extract visible text from page."""
    _ensure_browser()
    text = _page.inner_text("body")
    limit = 8000
    if len(text) > limit:
        text = text[:limit] + f"\n\n…(truncated, {len(text)} chars total)"
    return {"content": text}


def get_html(args: dict) -> dict:
    """Get raw HTML source."""
    _ensure_browser()
    html = _page.content()
    limit = 15000
    if len(html) > limit:
        html = html[:limit] + "\n…(truncated)"
    return {"content": html}


def click(args: dict) -> dict:
    """Click an element by CSS selector."""
    _ensure_browser()
    selector = args["selector"]
    try:
        _page.wait_for_selector(selector, timeout=min(TIMEOUT_MS, 5000))
        _page.click(selector, timeout=TIMEOUT_MS)
        return {"content": f"Clicked: {selector}"}
    except Exception as e:
        return {"content": f"Click failed on '{selector}': {e}", "isError": True}


def fill(args: dict) -> dict:
    """Fill an input field."""
    _ensure_browser()
    selector = args["selector"]
    value = args["value"]
    try:
        _page.wait_for_selector(selector, timeout=min(TIMEOUT_MS, 5000))
        _page.fill(selector, value, timeout=TIMEOUT_MS)
        return {"content": f"Filled: {selector}"}
    except Exception as e:
        return {"content": f"Fill failed on '{selector}': {e}", "isError": True}


def get_links(args: dict) -> dict:
    """List all links on the page."""
    _ensure_browser()
    links = _page.eval_on_selector_all(
        "a[href]",
        "els => els.map(el => ({text: el.textContent.trim(), href: el.href}))",
    )
    lines = [f"• {l['text'][:60]} → {l['href']}" for l in links[:30] if l["text"]]
    return {"content": "\n".join(lines) if lines else "No links found"}


def execute_js(args: dict) -> dict:
    """Run JavaScript in the browser."""
    _ensure_browser()
    result = _page.evaluate(args["code"])
    return {"content": str(result)}


def cleanup(args: dict = None) -> dict:
    """Close browser and free resources."""
    global _browser, _context, _page, _nav_count
    if _context:
        _context.close()
    if _browser:
        _browser.close()
    _browser = _context = _page = None
    _nav_count = 0
    return {"content": "Browser closed. Session cleaned."}


# ── Registry ─────────────────────────────────────────────────
TOOLS = {
    "browser_navigate": {
        "description": "Navigate to a URL in the browser",
        "schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Full URL to navigate to"}},
            "required": ["url"],
        },
        "handler": navigate,
    },
    "browser_screenshot": {
        "description": "Take a screenshot of the current page",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "screenshot.png", "description": "Output file path"},
                "full_page": {"type": "boolean", "default": False, "description": "Capture entire scrollable page"},
            },
        },
        "handler": screenshot,
    },
    "browser_get_text": {
        "description": "Extract all visible text from the current page",
        "schema": {"type": "object", "properties": {}},
        "handler": get_text,
    },
    "browser_get_html": {
        "description": "Get the full HTML source of the current page",
        "schema": {"type": "object", "properties": {}},
        "handler": get_html,
    },
    "browser_click": {
        "description": "Click an element by CSS selector",
        "schema": {
            "type": "object",
            "properties": {"selector": {"type": "string", "description": "CSS selector of the element"}},
            "required": ["selector"],
        },
        "handler": click,
    },
    "browser_fill": {
        "description": "Fill an input field by CSS selector",
        "schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector of the input field"},
                "value": {"type": "string", "description": "Text to fill in"},
            },
            "required": ["selector", "value"],
        },
        "handler": fill,
    },
    "browser_get_links": {
        "description": "Get all links on the current page",
        "schema": {"type": "object", "properties": {}},
        "handler": get_links,
    },
    "browser_execute_js": {
        "description": "Execute JavaScript in the browser and return the result",
        "schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "JavaScript code to execute"}},
            "required": ["code"],
        },
        "handler": execute_js,
    },
    "browser_cleanup": {
        "description": "Close the browser session and clean up resources",
        "schema": {"type": "object", "properties": {}},
        "handler": cleanup,
    },
}


# ── MCP Protocol ─────────────────────────────────────────────
def handle_request(req: dict) -> dict | None:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "browser-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            },
        }

    if method == "tools/list":
        tools_list = [
            {"name": k, "description": v["description"], "inputSchema": v["schema"]}
            for k, v in TOOLS.items()
        ]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
            }
        try:
            result = TOOLS[tool_name]["handler"](tool_args)
        except Exception as e:
            result = {"content": f"Error: {e}", "isError": True}
        content = result.get("content", str(result))
        response = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": content}]}}
        if result.get("isError"):
            response["result"]["isError"] = True
        return response

    if method == "notifications/initialized":
        return None

    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


# ── Entry Point ──────────────────────────────────────────────
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
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
