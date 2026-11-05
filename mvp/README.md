# AI78QA — Lightweight MVP

This is a small, independent first version of AI78QA. It does not use Docker, Redis, PostgreSQL, Celery, Next.js, or a cloud service.

## Requirements

- Windows 10/11
- Python 3.11 or newer
- Internet access for installing Python packages and Chromium

## Start on Windows

Open PowerShell in the repository and run:

```powershell
cd mvp
Set-ExecutionPolicy -Scope Process Bypass -Force
.\run.ps1
```

The script creates a virtual environment, installs Flask and Playwright, downloads Chromium, and starts the app.

Open **http://127.0.0.1:5000**.

## Manual setup

```powershell
cd mvp
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python app.py
```

## Current features

- URL-based website discovery
- Same-origin breadth-first page crawling (up to 500 pages per scan; choose 25, 50, 100, 250 or 500)
- Page titles and headings
- Links, buttons, input fields, dropdown options and forms
- Table headers and page landmarks
- Full-page screenshots
- Authenticated same-origin crawling using the live post-login session
- Safe exploration of visible menus, tabs, accordions, details and other low-risk controls, recording observed state changes
- Passive capture of same-origin network requests and API-like endpoint URLs
- Detailed Markdown discovery report and complete JSON report
- Extracted link inventory per page, including links revealed by safe menu interactions and a Markdown discovery document with page-by-page details
- Local-only dashboard

## Deliberate MVP limitations

- Detects visible password forms on the starting page and same-origin sign-in links
- Prompts the user for username/email and password when a standard login form is detected
- Reuses the authenticated browser session for same-origin discovery; credentials are never written to reports or browser storage
- Starts crawling from the actual post-login destination (for example, an inventory/dashboard URL) rather than reloading the login URL
- Distinguishes a real login form from an arbitrary password field to reduce false session-expiry errors
- Masks input and textarea fields in screenshots (other account-page content may still be visible)
- No application form submission or destructive business interactions (purchases, payments, sending messages, deleting records, or logout)
- Safe UI exploration is heuristic and does not guarantee every control or business workflow is covered
- Crawling is limited to 500 pages per run; external domains are recorded but not crawled
- API discovery is passive: requests are observed, not replayed, fuzzed, or attacked
- No AI-generated test cases yet
- No automated pass/fail assertions
- Standard single-page username/password forms are supported; OTP, CAPTCHA, SSO, MFA and multi-step login flows may require manual handling
- JavaScript-heavy sites are inspected after initial page load
- No multi-user access or remote deployment

Credentials are sent only to the local Flask process for the duration of the scan and are not persisted. Use a dedicated test account, never a personal or production account. Screenshots mask form inputs but can still contain account data elsewhere on the page. This is an observation-only discovery baseline. It does not submit application forms or perform destructive actions. Use it only on websites you own or are authorized to test.
