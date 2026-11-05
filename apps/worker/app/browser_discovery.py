from __future__ import annotations
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from app.database import SessionLocal
from app.models import TrainingSession, TrainingWebsite, Observation

def public_host(host: str) -> bool:
    if host.lower() in {"localhost", "metadata.google.internal"} or host.lower().endswith(".localhost"):
        return False
    try:
        ips = {item[4][0] for item in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        return False
    for value in ips:
        ip = ipaddress.ip_address(value)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True

async def explore(session_id: str) -> dict:
    db = SessionLocal()
    try:
        session = db.get(TrainingSession, session_id)
        if not session:
            return {"status": "not_found"}
        site = db.get(TrainingWebsite, session.website_id)
        host = urlparse(site.base_url).hostname
        if not host or not public_host(host):
            session.status = "blocked"
            session.summary = {"reason": "Target is not a public host."}
            db.commit()
            return {"status": "blocked"}
        session.status = "running"
        db.commit()
        queue = [(site.base_url, 0)]
        visited = set()
        page_count = element_count = 0
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(8000)
            while queue and page_count < session.max_pages:
                url, depth = queue.pop(0)
                if urlparse(url).hostname != host or url in visited or depth > session.max_depth:
                    continue
                visited.add(url)
                if not public_host(host):
                    continue
                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    if urlparse(page.url).hostname != host or (response and response.status >= 400):
                        continue
                    data = await page.evaluate("""() => ({
                      title: document.title || '',
                      elements: Array.from(document.querySelectorAll('button,a,input,select,textarea,[role],[data-testid]')).slice(0,400).map(el => {
                        const r=el.getBoundingClientRect(), s=getComputedStyle(el), tag=el.tagName.toLowerCase();
                        const type=el.getAttribute('type')||'', role=el.getAttribute('role')||'';
                        const name=el.getAttribute('aria-label')||el.innerText||el.getAttribute('placeholder')||el.getAttribute('name')||'';
                        return {tag,role,type,name:String(name).trim().slice(0,240),test_id:el.getAttribute('data-testid'),visible:r.width>0&&r.height>0&&s.visibility!=='hidden',enabled:!el.disabled,unique_hint:!!el.id,href:tag==='a'?el.href:null};
                      })
                    })""")
                    for item in data["elements"]:
                        db.add(Observation(session_id=session.id,page_url=page.url,page_title=data["title"],element_type=item.get("role") or item.get("tag","unknown"),semantic_name=item.get("name",""),features=item,source="browser_observation",label_verified=False))
                    links = await page.locator("a[href]").evaluate_all("(els)=>els.map(a=>a.href).slice(0,150)")
                    for link in links:
                        parsed = urlparse(link)
                        if parsed.scheme in {"http","https"} and parsed.hostname == host and link not in visited:
                            queue.append((link,depth+1))
                    page_count += 1
                    element_count += len(data["elements"])
                    db.commit()
                except Exception:
                    db.rollback()
            await context.close()
            await browser.close()
        session = db.get(TrainingSession,session_id)
        session.status = "completed" if page_count else "blocked"
        session.summary = {"pages_discovered":page_count,"elements_observed":element_count,"visited_urls":sorted(visited),"labels_verified":0,"mode":"observe","note":"Raw observations require verified labels before model training."}
        db.commit()
        return {"status":session.status,**session.summary}
    except Exception:
        db.rollback()
        session = db.get(TrainingSession,session_id)
        if session:
            session.status = "failed"
            session.summary = {"error":"Browser exploration failed; sensitive details suppressed."}
            db.commit()
        return {"status":"failed"}
    finally:
        db.close()

def run_exploration(session_id: str):
    return asyncio.run(explore(session_id))
