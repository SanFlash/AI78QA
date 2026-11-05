# AI78QA architecture

## Product domains
1. Training Lab: website registry, scoped exploration, raw observations, verified labels, datasets, experiments, evaluations and model registry.
2. Project QA: requirements, module/feature inventory, manual test plans, canonical test specifications, automation repositories, execution and defects.
3. Execution: asynchronous queue, isolated browser worker, Playwright primary, Selenium adapter, evidence collector and policy engine.
4. Intelligence: provider-agnostic LLM, classical ML inference, application knowledge store and feedback curation.
5. Reporting: canonical result store with HTML, JSON, DOCX, PDF, Excel and Allure export adapters.

## Learning boundary
Global models learn general UI patterns. Application knowledge stores site-specific pages, workflows and roles. Customer data is not silently mixed into global training.

## Safety
Only explicitly authorized targets. Restrict DNS/IP destinations, redirects, external links, browser downloads, forms and destructive actions. Enforce egress policy at the network level too. LLM output is untrusted and cannot bypass the policy engine.

Browser jobs must run in isolated worker containers, never in API request handlers.
