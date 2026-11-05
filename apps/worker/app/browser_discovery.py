from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
import socket
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from app.database import SessionLocal
from app.models import TrainingSession, TrainingWebsite, Observation

SAFE_ACTION_WORDS = {"open", "show", "view", "menu", "tab", "expand", "collapse", "filter", "sort", "next", "previous", "details", "more", "less", "toggle", "close", "back", "forward"}
DANGEROUS_WORDS = {
    "delete", "remove", "destroy", "purchase", "buy now", "pay now",
    "checkout", "place order", "submit payment", "transfer", "send",
    "publish", "invite", "revoke", "cancel subscription", "sign out", "log out",
}
SAFE_CLICK_SELECTOR = (
    "button:not([type=submit]):not([type=reset]),"
    "[role=button], [role=tab], [aria-expanded], summary,"
    "[data-toggle], [data-bs-toggle]"
)
MAX_INTERACTIONS_PER_PAGE = 24
MAX_ELEMENTS_PER_PAGE = 500
MAX_LINKS_PER_PAGE = 250


def public_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    if not host or host == "localhost" or host.endswith((".localhost", ".local")):
        return False
    try:
        addresses = {entry[4][0] for entry in socket.getaddrinfo(host, None)}
    except (socket.gaierror, OSError):
        return False
    if not addresses:
        return False
    for value in addresses:
        ip = ipaddress.ip_address(value)
        if not ip.is_global:
            return False
    return True


def canonical_url(raw: str, base: str, allowed_host: str) -> str | None:
    try:
        absolute = urldefrag(urljoin(base, raw))[0]
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.hostname != allowed_host:
            return None
        if parsed.username or parsed.password or not public_host(parsed.hostname):
            return None
        # Drop common analytics parameters while preserving application state/query parameters.
        pairs = []
        sensitive_keys = {"token", "access_token", "refresh_token", "id_token", "code", "key",
                          "api_key", "secret", "password", "session", "sessionid", "auth",
                          "signature", "sig", "state", "nonce"}
        for item in parsed.query.split("&") if parsed.query else []:
            key = item.split("=", 1)[0].lower()
            if key.startswith("utm_") or key in {"gclid", "fbclid", "ref_src"} or key in sensitive_keys:
                continue
            pairs.append(item)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, "&".join(pairs), ""))
    except Exception:
        return None


def stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def redact_text(value: str) -> str:
    value = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[REDACTED_EMAIL]", value, flags=re.I)
    value = re.sub(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)", "[REDACTED_PHONE_OR_NUMBER]", value)
    value = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[REDACTED_PAYMENT_NUMBER]", value)
    return value[:6000]


def scrub_snapshot(snapshot: dict, base_url: str, allowed_host: str) -> dict:
    def scrub(value):
        if isinstance(value, str):
            return redact_text(value)
        if isinstance(value, list):
            return [scrub(item) for item in value]
        if isinstance(value, dict):
            cleaned = {}
            for key, item in value.items():
                if key in {"href", "url"} and isinstance(item, str):
                    cleaned[key] = canonical_url(item, base_url, allowed_host)
                else:
                    cleaned[key] = scrub(item)
            return cleaned
        return value
    return scrub(snapshot)


async def install_request_guard(context, allowed_host: str):
    async def guard(route):
        request = route.request
        parsed = urlparse(request.url)
        host = parsed.hostname
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or host != allowed_host
            or not public_host(host)
            or parsed.username
            or parsed.password
        ):
            await route.abort("blockedbyclient")
            return
        await route.continue_()
    await context.route("**/*", guard)


async def page_snapshot(page) -> dict:
    return await page.evaluate("""() => {
      const visible = el => {
        const r = el.getBoundingClientRect(), s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
      };
      const clean = value => String(value || '').replace(/\\s+/g, ' ').trim().slice(0, 300);
      const nodes = Array.from(document.querySelectorAll(
        'a[href],button,input,select,textarea,[role],summary,[tabindex],[contenteditable=true],[data-testid]'
      )).slice(0, 500);
      const elements = nodes.map((el, index) => {
        const tag = el.tagName.toLowerCase(), role = el.getAttribute('role') || '';
        const label = el.getAttribute('aria-label') ||
          el.getAttribute('aria-labelledby') ||
          el.labels?.[0]?.innerText ||
          el.innerText || el.getAttribute('placeholder') ||
          el.getAttribute('name') || el.getAttribute('title') || '';
        const r = el.getBoundingClientRect();
        const href = tag === 'a' ? el.href : null;
        const item = {
          index, tag, role, type: el.getAttribute('type') || '',
          name: clean(label), text: clean(el.innerText), placeholder: clean(el.getAttribute('placeholder')),
          id: el.id || null, test_id: el.getAttribute('data-testid'),
          name_attr: el.getAttribute('name'), href,
          visible: visible(el), enabled: !el.disabled && el.getAttribute('aria-disabled') !== 'true',
          checked: 'checked' in el ? !!el.checked : null,
          expanded: el.getAttribute('aria-expanded'),
          selected: el.getAttribute('aria-selected'),
          value_present: 'value' in el && !!el.value,
          bounds: {x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height)}
        };
        return item;
      });
      const headings = Array.from(document.querySelectorAll('h1,h2,h3')).slice(0, 60)
        .filter(visible).map(el => ({level: Number(el.tagName[1]), text: clean(el.innerText)}));
      const forms = Array.from(document.forms).map((form, index) => ({
        index, name: clean(form.getAttribute('aria-label') || form.name || form.id),
        method: (form.method || 'get').toUpperCase(),
        fields: Array.from(form.elements).filter(el => el.name || el.id).slice(0, 80).map(el => ({
          name: el.name || el.id, type: el.type || el.tagName.toLowerCase(),
          required: !!el.required, disabled: !!el.disabled,
          label: clean(el.labels?.[0]?.innerText || el.getAttribute('aria-label') || el.placeholder)
        }))
      }));
      return {
        title: document.title || '', url: location.href,
        description: document.querySelector('meta[name=description]')?.content || '',
        headings, forms, elements,
        body_text: clean(document.body?.innerText).slice(0, 6000)
      };
    }""")


async def explore(session_id: str) -> dict:
    db = SessionLocal()
    browser = context = None
    try:
        session = db.get(TrainingSession, session_id)
        if not session:
            return {"status": "not_found"}
        site = db.get(TrainingWebsite, session.website_id)
        parsed = urlparse(site.base_url)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or not public_host(host):
            session.status = "blocked"
            session.summary = {"reason": "Target is not a verified public HTTP(S) host."}
            db.commit()
            return {"status": "blocked"}

        session.status = "running"
        session.started_at = datetime.now(timezone.utc)
        db.commit()

        allowed_domains = set(site.allowed_domains or [host])
        if host not in allowed_domains:
            session.status = "blocked"
            session.summary = {"reason": "Target host is not in the approved domain list."}
            db.commit()
            return {"status": "blocked"}

        queue = deque([(site.base_url, 0, "entry")])
        queued = {canonical_url(site.base_url, site.base_url, host) or site.base_url}
        visited = set()
        page_count = element_count = interaction_count = transition_count = 0
        blocked_count = error_count = 0
        route_inventory = []
        console_errors = []
        request_failures = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                ignore_https_errors=False,
                service_workers="block",
            )
            await install_request_guard(context, host)
            page = await context.new_page()
            page.set_default_timeout(5000)
            page.on("console", lambda msg: console_errors.append(redact_text(msg.text)[:500]) if msg.type == "error" and len(console_errors) < 50 else None)
            page.on("requestfailed", lambda req: request_failures.append({"url": urlunparse((*urlparse(req.url)[:4], "", ""))[:500], "failure": (req.failure or "")[:200]}) if len(request_failures) < 50 else None)

            while queue and page_count < session.max_pages:
                url, depth, discovered_from = queue.popleft()
                normalized = canonical_url(url, site.base_url, host)
                if not normalized or normalized in visited or depth > session.max_depth:
                    continue
                visited.add(normalized)
                try:
                    if not public_host(host):
                        blocked_count += 1
                        continue
                    response = await page.goto(normalized, wait_until="domcontentloaded", timeout=20000)
                    if page.url and urlparse(page.url).hostname != host:
                        blocked_count += 1
                        continue
                    if response and response.status >= 400:
                        error_count += 1
                        continue
                    try:
                        await page.locator("body").wait_for(state="visible", timeout=4000)
                    except PlaywrightTimeoutError:
                        pass
                    await page.wait_for_timeout(350)
                    snapshot = scrub_snapshot(await page_snapshot(page), site.base_url, host)
                    evidence_root = Path(os.getenv("EVIDENCE_DIR", "/data/evidence")) / session.id
                    evidence_root.mkdir(parents=True, exist_ok=True)
                    page_evidence_name = None
                    evidence_enabled = False
                    try:
                        await page.add_style_tag(content="""
                          input, textarea, select, [type=password], [autocomplete*=email],
                          [autocomplete*=tel], [autocomplete*=cc-], [data-private] {
                            filter: blur(8px) !important; color: transparent !important; text-shadow: none !important;
                          }
                        """)
                        page_evidence_name = f"page-{page_count + 1:04d}.png"
                        await page.screenshot(path=str(evidence_root / page_evidence_name), full_page=False, animations="disabled")
                        evidence_enabled = True
                    except Exception:
                        # Do not save an unmasked screenshot or fail the crawl when screenshot capture is unavailable.
                        page_evidence_name = None
                    current_url = canonical_url(page.url, site.base_url, host) or normalized
                    page_key = stable_hash({"url": current_url, "title": snapshot["title"], "headings": snapshot["headings"]})
                    route_inventory.append({"url": current_url, "title": snapshot["title"], "depth": depth, "discovered_from": discovered_from, "page_key": page_key})

                    db.add(Observation(
                        session_id=session.id, page_url=current_url, page_title=snapshot["title"],
                        element_type="page_snapshot", semantic_name=snapshot["title"] or current_url,
                        features={"kind": "page_snapshot", "page_key": page_key, "description": snapshot["description"],
                                  "headings": snapshot["headings"], "forms": snapshot["forms"],
                                  "body_text": snapshot["body_text"], "element_count": len(snapshot["elements"]),
                                  "discovered_from": discovered_from, "depth": depth,
                                  "evidence_file": page_evidence_name},
                        source="page_snapshot", label_verified=False
                    ))

                    for item in snapshot["elements"]:
                        db.add(Observation(
                            session_id=session.id, page_url=current_url, page_title=snapshot["title"],
                            element_type=item.get("role") or item.get("tag", "unknown"),
                            semantic_name=item.get("name") or item.get("text") or item.get("placeholder") or "",
                            features={"kind": "ui_element", **item}, source="ui_inventory", label_verified=False
                        ))
                        if item.get("href"):
                            target = canonical_url(item["href"], current_url, host)
                            if target and target not in queued and target not in visited and len(queued) < 3000:
                                queued.add(target)
                                queue.append((target, depth + 1, current_url))

                    page_count += 1
                    element_count += len(snapshot["elements"])
                    db.commit()

                    # Explore state-changing UI affordances only; never submit forms or activate destructive actions.
                    await page.evaluate("""(selector) => {
                      document.querySelectorAll(selector).forEach((el, i) => {
                        if (!el.hasAttribute('data-ai78qa-node')) el.setAttribute('data-ai78qa-node', String(i));
                      });
                    }""", SAFE_CLICK_SELECTOR)
                    candidate_count = await page.locator(SAFE_CLICK_SELECTOR).count()
                    limit = min(candidate_count, MAX_INTERACTIONS_PER_PAGE)
                    for idx in range(limit):
                        locator = page.locator(SAFE_CLICK_SELECTOR).nth(idx)
                        try:
                            if not await locator.is_visible() or not await locator.is_enabled():
                                continue
                            before = scrub_snapshot(await page_snapshot(page), site.base_url, host)
                            target = await locator.evaluate("""el => ({
                              tag: el.tagName.toLowerCase(),
                              role: el.getAttribute('role') || '',
                              name: (el.getAttribute('aria-label') || el.innerText || el.title || '').replace(/\\s+/g,' ').trim().slice(0,180),
                              type: el.getAttribute('type') || '',
                              expanded: el.getAttribute('aria-expanded'),
                              selected: el.getAttribute('aria-selected')
                            })""")
                            words = (target.get("name") or "").lower()
                            expanded_control = await locator.get_attribute("aria-expanded")
                            safe_semantic_control = (
                                target.get("role") == "tab"
                                or expanded_control is not None
                                or await locator.evaluate("(el) => el.tagName.toLowerCase() === 'summary' || el.hasAttribute('data-toggle') || el.hasAttribute('data-bs-toggle')")
                                or any(word in words for word in SAFE_ACTION_WORDS)
                            )
                            if (not safe_semantic_control or target.get("type") in {"submit", "reset"}
                                or any(word in words for word in DANGEROUS_WORDS)):
                                continue
                            # Only interact with explicit UI controls, not arbitrary clickable containers.
                            before_url = canonical_url(page.url, site.base_url, host) or current_url
                            before_key = stable_hash({"url": before_url, "body": before["body_text"], "elements": [(x["tag"],x["name"],x["expanded"],x["selected"]) for x in before["elements"][:100]]})
                            await locator.click(timeout=1800, no_wait_after=True)
                            await page.wait_for_timeout(250)
                            after_url = canonical_url(page.url, site.base_url, host)
                            if not after_url:
                                await page.go_back(wait_until="domcontentloaded", timeout=5000)
                                continue
                            after = scrub_snapshot(await page_snapshot(page), site.base_url, host)
                            # Menus, tabs and accordions often reveal routes absent from the initial DOM.
                            revealed_links = await page.locator("a[href]").evaluate_all("(els) => els.map(a => a.href).slice(0, 250)")
                            for revealed in revealed_links:
                                discovered = canonical_url(revealed, after_url, host)
                                if discovered and discovered not in queued and discovered not in visited and len(queued) < 3000:
                                    queued.add(discovered)
                                    queue.append((discovered, depth + 1, after_url))
                            after_key = stable_hash({"url": after_url, "body": after["body_text"], "elements": [(x["tag"],x["name"],x["expanded"],x["selected"]) for x in after["elements"][:100]]})
                            transition_evidence_name = None
                            if before_key != after_key and evidence_enabled:
                                candidate_evidence_name = f"state-{interaction_count + 1:04d}.png"
                                try:
                                    await page.screenshot(path=str(evidence_root / candidate_evidence_name), full_page=False, animations="disabled")
                                    transition_evidence_name = candidate_evidence_name
                                except Exception:
                                    transition_evidence_name = None
                            changed = before_key != after_key
                            interaction_count += 1
                            if changed:
                                transition_count += 1
                            db.add(Observation(
                                session_id=session.id, page_url=before_url, page_title=before["title"],
                                element_type=target.get("role") or target.get("tag") or "control",
                                semantic_name=target.get("name") or "Unnamed control",
                                features={"kind": "interaction_transition", "action": "click", "target": target,
                                          "before_state": before_key, "after_state": after_key,
                                          "before_url": before_url, "after_url": after_url,
                                          "state_changed": changed, "after_headings": after["headings"][:20],
                                          "after_body_text": after["body_text"][:1800],
                                          "evidence_file": transition_evidence_name},
                                source="interaction_transition", label_verified=False
                            ))
                            db.commit()
                            # A navigation or modal state is recorded; return to the original page before the next candidate.
                            if after_url != before_url:
                                await page.goto(before_url, wait_until="domcontentloaded", timeout=10000)
                                await page.wait_for_timeout(150)
                        except PlaywrightTimeoutError:
                            db.rollback()
                            continue
                        except Exception:
                            db.rollback()
                            continue

                except PlaywrightTimeoutError:
                    error_count += 1
                    db.rollback()
                    continue
                except Exception:
                    error_count += 1
                    db.rollback()
                    continue

            await context.close()
            await browser.close()
            browser = context = None

        session = db.get(TrainingSession, session_id)
        session.status = "completed" if page_count else "blocked"
        session.completed_at = datetime.now(timezone.utc)
        session.summary = {
            "pages_discovered": page_count, "elements_observed": element_count,
            "interactions_attempted": interaction_count, "state_transitions_observed": transition_count,
            "unique_urls_queued": len(queued), "blocked_navigation_count": blocked_count,
            "page_errors": error_count, "routes": route_inventory,
            "console_errors": console_errors[:30], "request_failures": request_failures[:30],
            "labels_verified": 0, "mode": "observe_and_safe_interact",
            "coverage_note": "Only same-host pages and non-destructive controls were explored. Authentication, hidden states and business outcomes may require a user-authenticated session and verified test data."
        }
        db.commit()
        return {"status": session.status, **session.summary}
    except Exception:
        db.rollback()
        session = db.get(TrainingSession, session_id)
        if session:
            session.status = "failed"
            session.completed_at = datetime.now(timezone.utc)
            session.summary = {"error": "Browser exploration failed; sensitive details suppressed."}
            db.commit()
        return {"status": "failed"}
    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()
        db.close()


def run_exploration(session_id: str):
    return asyncio.run(explore(session_id))
