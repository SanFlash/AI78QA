from __future__ import annotations

import json
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


def wait_for_page(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=2500)
    except PlaywrightTimeoutError:
        pass


def visible_login_form(page) -> bool:
    """Detect a login form, not merely any password field on the page."""
    password = page.locator('input[type="password"]:visible').first
    if not password.count():
        return False
    form = password.locator("xpath=ancestor::form[1]")
    if form.count():
        try:
            return form.locator('button[type="submit"], input[type="submit"], button').count() > 0
        except Exception:
            pass
    # Some SPA login pages do not wrap fields in a form.
    return find_username_field(page) is not None or page.locator(
        'button:has-text("Login"), button:has-text("Log in"), button:has-text("Sign in")'
    ).count() > 0


def locate_login_page(page, start_url: str) -> str | None:
    """Check the start page, then a few same-origin sign-in links for a password form."""
    page.goto(start_url, wait_until="domcontentloaded", timeout=25000)
    wait_for_page(page)
    if visible_login_form(page):
        return page.url

    candidates = page.locator("a[href]").evaluate_all("""links => links.map(a => ({
      href: a.href,
      text: (a.innerText || a.textContent || '').trim()
    }))""")
    seen = set()
    for item in candidates:
        href = clean_url(item.get("href", ""))
        label = f"{item.get('text', '')} {href}".lower()
        if not any(term in label for term in ("login", "log-in", "sign in", "signin", "my-account")):
            continue
        if "logout" in label or href in seen or not same_origin(start_url, href):
            continue
        seen.add(href)
        try:
            page.goto(href, wait_until="domcontentloaded", timeout=15000)
            wait_for_page(page)
            if visible_login_form(page):
                return page.url
        except Exception:
            continue

    page.goto(start_url, wait_until="domcontentloaded", timeout=25000)
    wait_for_page(page)
    return None


def inspect_page(page, url: str) -> dict:
    # Do not reload the authenticated landing page: retain the live post-login state.
    if clean_url(page.url) != clean_url(url):
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        wait_for_page(page)

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



def explore_safe_interactions(page, page_url: str, limit: int = 20) -> list[dict]:
    """Explore low-risk UI controls and record the observed state change.

    This deliberately excludes submit, purchase, delete, save, send, logout,
    payment and other business-transaction controls.
    """
    candidates = page.evaluate("""() => {
      const visible = el => {
        const r = el.getBoundingClientRect(), s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
      };
      const label = el => (el.innerText || el.textContent || el.getAttribute('aria-label') || el.title || '').trim().replace(/\\s+/g, ' ').slice(0, 100);
      const safe = /^(menu|navigation|open menu|close menu|tab|show|view|view details|details|expand|collapse|more|less|filter|sort|accordion|preferences|settings)$/i;
      const nodes = [...document.querySelectorAll('button,[role="button"],[role="tab"],summary,[aria-expanded="false"]')];
      return nodes.filter(visible).map((el, index) => ({
        index, label: label(el), role: el.getAttribute('role') || el.tagName.toLowerCase(),
        expanded: el.getAttribute('aria-expanded'), disabled: !!el.disabled,
        text: label(el)
      })).filter(x => !x.disabled && (safe.test(x.label) || /^(menu|tab|button)$/.test(x.role) && safe.test(x.text)));
    }""")
    results = []
    original_url = clean_url(page.url or page_url)
    for item in candidates[:limit]:
        try:
            before = page.evaluate("""() => ({
              url: location.href, title: document.title,
              active: [...document.querySelectorAll('[role="tab"][aria-selected="true"],[aria-current="page"],.active')].slice(0,12).map(e => (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0,80)),
              dialogs: [...document.querySelectorAll('[role="dialog"],dialog[open]')].filter(e => e.getBoundingClientRect().width).map(e => (e.innerText || '').trim().slice(0,500))
            })""")
            clicked = page.evaluate("""index => {
              const visible = el => { const r=el.getBoundingClientRect(),s=getComputedStyle(el); return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none'; };
              const nodes=[...document.querySelectorAll('button,[role="button"],[role="tab"],summary,[aria-expanded="false"]')].filter(visible);
              const el=nodes[index]; if (!el || el.disabled) return false;
              el.click(); return true;
            }""", item["index"])
            if not clicked:
                continue
            page.wait_for_timeout(350)
            after = page.evaluate("""() => ({
              url: location.href, title: document.title,
              active: [...document.querySelectorAll('[role="tab"][aria-selected="true"],[aria-current="page"],.active')].slice(0,12).map(e => (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0,80)),
              dialogs: [...document.querySelectorAll('[role="dialog"],dialog[open]')].filter(e => e.getBoundingClientRect().width).map(e => (e.innerText || '').trim().slice(0,500)),
              expanded: [...document.querySelectorAll('[aria-expanded="true"]')].slice(0,15).map(e => (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0,80)),
              visibleText: (document.body.innerText || '').slice(0,1200)
            })""")
            results.append({"control": item["label"], "role": item["role"], "before": before, "after": after,
                            "observed_change": before != {k: after.get(k) for k in before}})
            # Reload the same-origin page to restore a predictable state, retaining cookies.
            if clean_url(page.url) != original_url or JSON.stringify(before) !== JSON.stringify(Object.fromEntries(Object.keys(before).map(k => [k, after[k]]))):
                page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
                wait_for_page(page)
        except Exception as exc:
            results.append({"control": item.get("label", ""), "error": str(exc)[:180]})
            try:
                if clean_url(page.url) != original_url:
                    page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
                    wait_for_page(page)
            except Exception:
                break
    return results


def find_username_field(page):
    selectors = [
        'input[autocomplete="username"]:visible',
        'input[type="email"]:visible',
        'input[name*="user" i]:visible',
        'input[id*="user" i]:visible',
        'input[name*="email" i]:visible',
        'input[id*="email" i]:visible',
        'input[type="text"]:visible'
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count():
            return locator
    return None


def login_feedback(page) -> str:
    selectors = [
        '[role="alert"]:visible',
        '[aria-live="assertive"]:visible',
        '.error-message-container:visible',
        '.error:visible',
        '.alert-danger:visible',
        '.invalid-feedback:visible',
        '[data-testid*="error" i]:visible'
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.count():
                message = locator.inner_text(timeout=1000).strip()
                if message:
                    return " ".join(message.split())[:300]
        except Exception:
            continue
    return ""


def authenticated_indicators(page) -> bool:
    selectors = [
        '[aria-label*="logout" i]:visible',
        'a[href*="logout" i]:visible',
        'button:has-text("Log out"):visible',
        'button:has-text("Logout"):visible',
        'button:has-text("Sign out"):visible',
        '[data-testid*="inventory" i]:visible',
        '[data-testid*="dashboard" i]:visible'
    ]
    for selector in selectors:
        try:
            if page.locator(selector).count():
                return True
        except Exception:
            continue
    return False


def submit_login(page, username: str, password: str) -> None:
    password_field = page.locator('input[type="password"]:visible').first
    if not password_field.count():
        raise ValueError("A visible password field was not found on the detected login page.")

    username_field = find_username_field(page)
    if username and username_field is not None:
        username_field.fill(username)
    password_field.fill(password)

    submit_selectors = [
        'button[type="submit"]:visible',
        'input[type="submit"]:visible',
        'button[id*="login" i]:visible',
        'button[name*="login" i]:visible',
        'input[id*="login" i]:visible',
        'button:has-text("Log in"):visible',
        'button:has-text("Login"):visible',
        'button:has-text("Sign in"):visible',
        'button:has-text("Continue"):visible',
        'button:has-text("Submit"):visible'
    ]

    submitted = False
    for selector in submit_selectors:
        try:
            button = page.locator(selector).first
            if button.count():
                button.click(timeout=5000)
                submitted = True
                break
        except Exception:
            continue

    if not submitted:
        try:
            password_field.press("Enter", timeout=3000)
        except Exception as exc:
            raise ValueError("Could not find a login submit button or submit the login form with Enter.") from exc

    # Wait for a real transition, a known authenticated marker, or an error message.
    for _ in range(10):
        page.wait_for_timeout(500)
        feedback = login_feedback(page)
        if feedback:
            raise ValueError(f"The website rejected the login: {feedback}")
        if not visible_login_form(page) or authenticated_indicators(page):
            return

    feedback = login_feedback(page)
    if feedback:
        raise ValueError(f"The website rejected the login: {feedback}")
    if visible_login_form(page):
        raise ValueError(
            "The login form is still visible after submission. The site may have rejected the credentials, require an extra step, or use a custom login flow. Check the website's message and try again."
        )


def save_screenshot(page, filename: str) -> None:
    # Hide form values in evidence screenshots. Use dedicated test accounts;
    # screenshots may still contain other page content from the test account.
    masks = page.locator("input, textarea").all()
    page.screenshot(
        path=str(REPORT_DIR / filename),
        full_page=True,
        animations="disabled",
        mask=masks
    )


def run_scan(start_url: str, max_pages: int, username: str = "", password: str = "") -> dict:
    visited = set()
    queue = deque()
    pages = []
    errors = []
    observed_requests = []
    authenticated_landing_url = start_url

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.on("request", lambda req: observed_requests.append({"method": req.method, "url": req.url, "resource_type": req.resource_type}) if same_origin(start_url, req.url) and len(observed_requests) < 500 else None)
        try:
            login_url = locate_login_page(page, start_url)
            if login_url:
                if not password:
                    return {"login_required": True, "login_url": login_url, "target": start_url}
                submit_login(page, username, password)
                wait_for_page(page)
                if visible_login_form(page):
                    feedback = login_feedback(page)
                    raise ValueError(
                        f"Login was not completed. {feedback or 'The login form is still displayed. Check the credentials or complete any additional authentication step.'}"
                    )
                authenticated_landing_url = clean_url(page.url)
                if not same_origin(start_url, authenticated_landing_url):
                    raise ValueError("After login, the website redirected outside the starting website origin. Discovery stopped for safety.")

            # Begin from the actual authenticated destination (for example /inventory.html),
            # not the original login URL. Keep the same browser context and session cookies.
            queue.append(authenticated_landing_url)

            while queue and len(pages) < max_pages:
                current = clean_url(queue.popleft())
                if current in visited:
                    continue
                visited.add(current)
                if not same_origin(start_url, current):
                    continue
                try:
                    result = inspect_page(page, current)
                    if visible_login_form(page):
                        errors.append({"url": current, "error": "This page redirected to a login form. The session may have expired or this area requires another permission."})
                        continue

                    result["interactive_exploration"] = explore_safe_interactions(page, result["url"])
                    for action in result["interactive_exploration"]:
                        destination = clean_url(action.get("after", {}).get("url", ""))
                        if destination and destination != current and same_origin(start_url, destination) and destination not in visited and destination not in queue:
                            queue.append(destination)
                    result["api_requests"] = [r for r in observed_requests if any(token in r["url"].lower() for token in ("/api/", "/graphql", "/rpc/", "/ajax/", "/rest/"))]
                    screenshot_name = f"page_{len(pages) + 1}.png"
                    save_screenshot(page, screenshot_name)
                    result["screenshot"] = screenshot_name
                    pages.append(result)

                    for link in result["links"]:
                        candidate = clean_url(urljoin(result["url"], link["href"]))
                        if same_origin(start_url, candidate) and candidate not in visited and candidate not in queue:
                            queue.append(candidate)
                except Exception as exc:
                    errors.append({"url": current, "error": str(exc)[:300]})
        finally:
            context.close()
            browser.close()

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": start_url,
        "authenticated_session": bool(password),
        "pages_scanned": len(pages),
        "errors_count": len(errors),
        "pages": pages,
        "errors": errors,
        "observed_same_origin_requests": observed_requests,
        "api_endpoints": sorted({r["url"] for r in observed_requests if any(token in r["url"].lower() for token in ("/api/", "/graphql", "/rpc/", "/ajax/", "/rest/"))}),
        "scope": "Same-origin authenticated discovery with safe UI exploration and passive request observation. Credentials are transient and are not saved. Business transactions, form submissions, purchases, messages, deletion, payment and logout actions are not executed."
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    report_path = REPORT_DIR / f"ai78qa_report_{stamp}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_file"] = report_path.name
    return report


@app.get("/")
def index():
    return render_template("index.html", report=None, error=None, login_required=False)


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
        if report.get("login_required"):
            return render_template(
                "index.html", report=None, error=None, login_required=True,
                login_url=report["login_url"], target=target, max_pages=max_pages
            )
        return render_template("index.html", report=report, error=None, login_required=False)
    except Exception as exc:
        return render_template("index.html", report=None, error=str(exc), login_required=False), 400


@app.post("/scan-authenticated")
def scan_authenticated():
    try:
        target = validate_target(request.form.get("url", ""))
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not password:
            raise ValueError("Enter the password to continue.")
        try:
            max_pages = int(request.form.get("max_pages", "5"))
        except ValueError:
            max_pages = 5
        max_pages = max(1, min(max_pages, 15))
        report = run_scan(target, max_pages, username=username, password=password)
        if report.get("login_required"):
            raise ValueError("The website is still requesting authentication. This login flow may need manual handling.")
        return render_template("index.html", report=report, error=None, login_required=False)
    except Exception as exc:
        return render_template("index.html", report=None, error=str(exc), login_required=False), 400


@app.get("/reports/<path:filename>")
def download_report(filename):
    from flask import send_from_directory
    return send_from_directory(REPORT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
