# Deep browser discovery engine

AI78QA discovery is a bounded, evidence-first crawl—not a link checker.

## What a training run does

1. Validates the target as HTTP(S), rejects URL credentials and non-public DNS destinations.
2. Starts an isolated headless Chromium context and blocks requests outside the exact approved hostname.
3. Crawls same-host anchors breadth-first within the configured page/depth budget.
4. Captures a page snapshot: URL/title/description, headings, forms and field metadata, visible interactive controls, accessibility hints, enabled/disabled state, links and visible text.
5. Records each element independently with its page and session provenance.
6. Safely exercises only low-risk UI affordances (tabs, expanded/collapsed controls, disclosure summaries, and controls with navigation/presentation semantics such as menu, open, view, expand, filter or sort).
7. Compares before/after state fingerprints and records observed transitions. Newly revealed links are added to the crawl queue.
8. Captures browser console errors and failed requests, bounded to a small sample.
9. Stores raw observations as unverified. The ML pipeline must not treat them as labels.

## API read models

- `GET /api/v1/training/sessions/{id}/observations?kind=ui_element&limit=100&offset=0`
- `GET /api/v1/training/sessions/{id}/discovery`

The discovery response includes page inventory, interaction transitions, and derived counts. Use pagination for large element inventories.

## Safety defaults

- Exact hostname scope; no external-domain crawl.
- Public-address checks on the API and worker request path.
- No form submission, payment, delete, publish, message send, or other destructive action.
- No credential guessing, CAPTCHA/MFA bypass, or authentication bypass.
- No arbitrary JavaScript execution sourced from the target page.
- Exploration limits are bounded by page/depth budgets and a per-page interaction cap.
- Raw UI observations are not verified business requirements and are not model-training labels.

The browser is not a substitute for network-level egress isolation. Production workers must run in a private container network with outbound policy controls, resource limits, per-run timeouts, and isolated storage.

## Current boundaries

This release does not yet provide a persistent authenticated browser profile, user-approved form/data-entry execution, screenshots/traces stored in object storage, cross-browser execution, API schema inference, accessibility conformance certification, or end-to-end business-flow assertions. It discovers and records UI-level transitions; a human or a verified oracle is still required to decide whether an outcome is correct.

For complete production use, deploy the API, PostgreSQL, Redis, worker and object storage together. Vercel hosts the Next.js control plane only; it is not the Playwright execution host.
