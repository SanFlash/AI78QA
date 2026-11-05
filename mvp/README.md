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
- Same-origin page crawling (1–15 pages)
- Page titles and headings
- Links, buttons, input fields, dropdown options and forms
- Table headers and page landmarks
- Full-page screenshots
- Downloadable JSON report
- Local-only dashboard

## Deliberate MVP limitations

- No login automation or credential storage
- No form submission or destructive interactions
- No AI-generated test cases yet
- No automated pass/fail assertions
- JavaScript-heavy sites are inspected after initial page load; authenticated areas are not explored
- No multi-user access or remote deployment

This is an observation-only discovery baseline. Use it only on websites you own or are authorized to test.
