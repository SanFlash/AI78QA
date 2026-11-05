from __future__ import annotations

import json
import os
import re
import socket
import ipaddress
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024


def validate_target(raw_url: str) -> str:
    value = (raw_url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a complete http:// or https:// website URL.")
    if parsed.username or parsed.password:
        raise ValueError("Do not put credentials inside the URL.")
    return value


def same_origin(first: str, second: str) -> bool:
    a, b = urlparse(first), urlparse(second)
    return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)


def clean_url(url: str) -> str:
    return urldefrag(url)[0]


def inspect_page(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=25000)
    try:
        page.wait_for_load_state("networkidle", timeout=2500)
    except PlaywrightTimeoutError:
        pass

    data = page.evaluate("""() => {
      const text = el => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 180);
      const attrs = el => ({
        tag: el.tagName.toLowerCase(),
        type: el.getAttribute('type') || '',
        name: el.getAttribute('name') || '',
        id: el.id || '',
        placeholder: el.getAttribute('placeholder') || '',
        ariaLabel: el.getAttribute('aria-label') || '',
        text: text(el),
        required: !!el.required
      });
      return {
        title: document.title || '',
        headings: [...document.querySelectorAll('h1,h2,h3')].slice(0, 40).map(text).filter(Boolean),
        links: [...document.querySelectorAll('a[href]')].slice(0, 150).map(a => ({
          text: text(a), href: a.href
        })).filter(a => a.href),
        buttons: [...document.querySelectorAll('button,[role="button"],input[type="button"],input[type="submit"]')].slice(0, 100).map(attrs),
        fields: [...document.querySelectorAll('input,textarea,select')].slice(0, 150).map(el => ({
          ...attrs(el),
          options: el.tagName === 'SELECT' ? [...el.options].slice(0, 30).map(o => ({text: text(o), value: o.value})) : []
        })),
        forms: [...document.forms].slice(0, 30).map(f => ({
          action: f.action || location.href,
          method: (f.method || 'get').toUpperCase(),
          fields: [...f.querySelectorAll('input,textarea,select,button')].length
        })),
        tables: [...document.querySelectorAll('table')].slice(0, 20).map(t => ({
          headers: [...t.querySelectorAll('th')].slice(0, 20).map(text),
          rows: t.querySelectorAll('tr').length
        })),
        landmarks: [...document.querySelectorAll('main,nav,header,footer,aside,[role="main"],[role="navigation"]')]
          .slice(0, 30).map(el => ({tag: el.tagName.toLowerCase(), role: el.getAttribute('role') || '', label: el.getAttribute('aria-label') || ''}))
      };
    }""")
    data["url"] = page.url
    data["screenshot"] = ""
    return data


def run_scan(start_url: str, max_pages: int) -> dict:
    visited = set()
    queue = deque([start_url])
    pages = []
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
        page = context.new_page()

        while queue and len(pages) < max_pages:
            current = clean_url(queue.popleft())
            if current in visited:
                continue
            visited.add(current)
            if not same_origin(start_url, current):
                continue
            try:
                result = inspect_page(page, current)
                screenshot_name = f"page_{len(pages) + 1}.png"
                screenshot_path = REPORT_DIR / screenshot_name
                page.screenshot(path=str(screenshot_path), full_page=True, animations="disabled")
                result["screenshot"] = screenshot_name
                pages.append(result)
                for link in result["links"]:
                    candidate = clean_url(urljoin(result["url"], link["href"]))
                    if same_origin(start_url, candidate) and candidate not in visited and candidate not in queue:
                        queue.append(candidate)
            except Exception as exc:
                errors.append({"url": current, "error": str(exc)[:300]})

        browser.close()

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": start_url,
        "pages_scanned": len(pages),
        "errors_count": len(errors),
        "pages": pages,
        "errors": errors,
        "scope": "Same-origin discovery only. No forms submitted and no destructive controls clicked."
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"ai78qa_report_{stamp}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_file"] = report_path.name
    return report


@app.get("/")
def index():
    return render_template("index.html", report=None, error=None)


@app.post("/scan")
def scan():
    try:
        target = validate_target(request.form.get("url", ""))
        try:
            max_pages = int(request.form.get("max_pages", "5"))
        except ValueError:
            max_pages = 5
        max_pages = max(1, min(max_pages, 15))
        report = run_scan(target, max_pages)
        return render_template("index.html", report=report, error=None)
    except Exception as exc:
        return render_template("index.html", report=None, error=str(exc)), 400


@app.get("/reports/<path:filename>")
def download_report(filename):
    from flask import send_from_directory
    return send_from_directory(REPORT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
