# OpenCode Browser MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.60%2B-2EAD33.svg)](https://playwright.dev/)
[![opencode](https://img.shields.io/badge/opencode-MCP-6366f1.svg)](https://opencode.ai)

**Give your AI coding agent eyes and hands on the web.** Built for [OpenCode](https://opencode.ai), works with any MCP-compatible AI agent.

- [中文文档](#中文) | [English](#english)

---

## English

A production-ready **Model Context Protocol (MCP)** server that lets AI agents browse the web, interact with pages, fill forms, and extract data. Built on Playwright for cross-browser reliability.

### Why This Exists

OpenCode is growing fast. There are browser MCPs for Claude Code (Chrome DevTools MCP, 44k★) and general-purpose tools (browser-use, 99k★). But nothing was purpose-built for OpenCode's workflow—until now.

### Features

| Feature | Detail |
|---------|--------|
| **30 Tools** | 7 categories: Navigation, Automation, Inspection, Debugging, Emulation, Performance, Management |
| **Snapshot + UIDs** | Accessibility-tree snapshot with unique element IDs — inspired by Chrome DevTools MCP |
| **Multi-Tab** | Open, switch, and close multiple browser tabs in one session |
| **Console & Network** | View browser console logs and network requests for full-stack debugging |
| **Cross-Browser** | Chromium, Firefox, WebKit — pick any via Playwright |
| **Device Emulation** | Mobile viewport, dark mode, geolocation spoofing, offline mode |
| **Headless by Default** | No visible window. Runs in the background |
| **Safety Sandbox** | Fresh browser instance per session. No cookies from host machine |
| **Domain Allowlist** | Restrict which sites the agent can access |
| **Auto-Cleanup** | Browser is closed and resources freed after each session |
| **Graceful Error Handling** | Sites blocking headless browsers are handled cleanly |

### Quick Start

```bash
# 1. Install dependencies
pip install playwright
python -m playwright install chromium

# 2. Add to your OpenCode config (~/.config/opencode/opencode.json)
```

```json
{
  "mcp": {
    "browser": {
      "type": "local",
      "command": ["python", "path/to/opencode-browser-mcp/browser_mcp.py"],
      "enabled": true,
      "environment": {
        "MCP_BROWSER_HEADLESS": "true",
        "MCP_BROWSER_TIMEOUT": "30000"
      }
    }
  }
}
```

```bash
# 3. Restart OpenCode and use via @
# Try: "Open https://example.com and tell me what the page says"
```

### Tools Reference

| Category | Tool | Description |
|----------|------|-------------|
| **Navigation** | `navigate_page` | Navigate to a URL |
| | `new_page` | Open a URL in a new tab |
| | `list_pages` | List all open tabs |
| | `select_page` | Switch to a tab by index |
| | `close_page` | Close a tab |
| | `wait_for` | Wait for text to appear on the page |
| | `handle_dialog` | Accept or dismiss browser dialogs |
| **Automation** | `take_snapshot` | Accessibility tree snapshot with element UIDs |
| | `click` | Click element by UID or CSS selector |
| | `fill` | Fill input field by UID or CSS selector |
| | `fill_form` | Batch fill multiple form fields at once |
| | `hover` | Hover over an element |
| | `drag` | Drag one element onto another |
| | `press_key` | Press a key or combination (e.g., `Enter`, `Control+A`) |
| | `type_text` | Type text using keyboard (emulates real typing) |
| | `upload_file` | Upload a file via a file input |
| **Inspection** | `screenshot` | Take a screenshot of page or element |
| | `get_text` | Extract all visible text |
| | `get_html` | Get full HTML source |
| | `get_links` | List all links on the page |
| | `execute_js` | Execute JavaScript and return result |
| **Debugging** | `list_console_messages` | List browser console logs (errors, warnings, info) |
| | `get_console_message` | Get a specific console message |
| | `list_network_requests` | List recent network requests (XHR, fetch, scripts) |
| | `get_network_request` | Get details of a network request |
| **Emulation** | `emulate` | Emulate device features (viewport, dark mode, geolocation, offline) |
| | `resize_page` | Resize the page viewport |
| **Performance** | `performance_start_trace` | Start measuring page load performance |
| | `performance_stop_trace` | Stop tracing and get Core Web Vitals metrics |
| **Management** | `cleanup` | Close browser and clean up all sessions |

**30 tools total** across 7 categories.

### Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `MCP_BROWSER_HEADLESS` | `true` | Hide browser window |
| `MCP_BROWSER_TIMEOUT` | `30000` | Navigation timeout (ms) |
| `MCP_BROWSER_MAX_NAVIGATIONS` | `10` | Max page loads per session |
| `MCP_BROWSER_ALLOWED_DOMAINS` | `*` | Comma-separated domain allowlist |

### Security

- No cookies from your main Chrome/Firefox are shared
- Each session starts with a fresh browser profile
- The agent can only access domains in the allowlist
- Set `MCP_BROWSER_ALLOWED_DOMAINS=github.com,localhost` for restricted access

---

## 中文

为 OpenCode 打造的浏览器 MCP 服务器。让 AI 编程助手可以浏览网页、填写表单、提取数据，基于 Playwright 跨浏览器运行。

### 特性

| 特性 | 详情 |
|------|------|
| **30 个工具** | 7 个类别：导航、自动化、检查、调试、模拟、性能、管理 |
| **快照 + UID** | 无障碍树快照 + 唯一元素 ID——借鉴 Chrome DevTools MCP 的设计 |
| **多标签页** | 同时打开、切换、关闭多个浏览器标签 |
| **控制台 & 网络** | 查看浏览器 console 日志和网络请求，实现全栈调试 |
| **跨浏览器** | Chromium / Firefox / WebKit 任选 |
| **设备模拟** | 移动端视口、暗色模式、GPS 伪装、离线模式 |
| **无头模式** | 默认不弹窗口，后台静默运行 |
| **安全沙箱** | 每次启动独立浏览器，不携带宿主机 Cookie |
| **域名白名单** | 限制 Agent 只能访问指定域名 |
| **自动清理** | 会话结束自动关闭浏览器释放资源 |
| **容错处理** | 优雅处理反爬网站 |

### 快速开始

```bash
pip install playwright
python -m playwright install chromium
```

将以下配置添加到 `~/.config/opencode/opencode.json`：

```json
{
  "mcp": {
    "browser": {
      "type": "local",
      "command": ["python", "path/to/opencode-browser-mcp/browser_mcp.py"],
      "enabled": true,
      "environment": {
        "MCP_BROWSER_HEADLESS": "true"
      }
    }
  }
}
```

### 使用示例

```
"打开 Bilibili 搜索 'AI Agent'，列出前 5 个视频标题"
"截图我的 portfolio 网站首页"
"在 Wikipedia 搜索 Artificial Intelligence 并摘录第一段"
"检查这个页面上有没有 JS 报错"
```

### 安全说明

- **默认不与主浏览器共享任何数据**——每次都是新会话
- 建议设置 `MCP_BROWSER_ALLOWED_DOMAINS` 限制访问范围
- 绝对不要连接已登录网银/邮箱的浏览器

---

## FAQ

**Q:** Can I use my main Chrome with this tool?  
**A:** Yes—set `HEADLESS=false`, but we recommend against it for privacy. The default sandbox mode uses Playwright's bundled Chromium, which has zero connection to your personal browser data.

**Q:** GitHub shows an error?  
**A:** GitHub blocks headless browsers aggressively. This is a GitHub limitation, not ours. We handle the error gracefully.

**Q:** How is this different from Chrome DevTools MCP?  
**A:** Chrome DevTools MCP is TypeScript-only, Chrome-only, and designed for frontend debugging. Our tool is Python-native, multi-browser, and designed for general web interaction with OpenCode.

| Feature | This Project | Chrome DevTools MCP | browser-use |
|---------|:---:|:---:|:---:|
| Language | Python | TypeScript | Python |
| Browsers | All | Chrome only | All |
| Snapshot + UIDs |   |   | — |
| Multi-tab |   |   | — |
| Console monitoring |   |   | — |
| Network inspection |   |   | — |
| Device emulation |   |   | — |
| Performance tracing |   |   | — |
| Core Web Vitals |   |   | — |
| Heap snapshots | — |   | — |
| Lighthouse audit | — |   | — |
| Open source | MIT | Apache 2.0 | MIT |
| Install size | ~5KB Python | ~500KB npm | ~25MB pip |

---

## License

MIT © [Hogan Dong](https://github.com/HoganDong486)
