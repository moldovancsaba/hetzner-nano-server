# Combined exchange results

This authenticated browser view uses only General Design System components, pinned to the package version in package-lock.json. It reads the factory's server-side snapshot proxy; a machine credential never reaches the browser. Refresh is manual. There is no browser polling or additional notification schedule.

Install using the existing private package-registry access, build with npm run build, and serve the resulting dist directory through the protected factory route /factory/exchange/. Keep /factory/exchange-snapshot behind the existing browser gate. Direct unauthenticated access must fail at that gate. Static responses disallow inline scripts; React and GDS styles use the factory's documented content policy.

The response reader enforces a byte bound while streaming and validates scopes, timestamps, nonnegative metrics, coverage and duplicate clients before displaying anything. A failed refresh retains the last verified snapshot. Source receipt, qualification, operation acceptance, confirmed fields and publication have distinct meanings. Missing evidence is explicit. No raw contacts or source page bodies are rendered.

Run Playwright with playwright.config.ts from the repository root after building. The tests use synthetic responses and cover keyboard skip/focus/refresh, automated accessibility, narrow/forced-color/reduced-motion error handling, dark-mode empty/stale states and malformed-response recovery. A manual screen-reader review remains a release check; automated accessibility is not a substitute.

Deployment requires the existing browser gate, factory snapshot configuration and private dashboard credential. Source production and gap tasks are independently disabled by default. See the canonical integration release manifest for separate business rollout gates.

For a metadata-only deployment, ops/deploy_metadata.py in the integration package installs the built assets directly behind the existing Caddy browser gate and injects a scoped snapshot credential only in its private server-side proxy snippet. This avoids restarting business workers. The helper defaults to a dry run, refuses an active/nonempty business exchange, takes a consistent private backup, validates the proxy and restores prior code/proxy on failure. Its --apply mode requires the private credential file and SSH access. The factory proxy remains available for installations using its configured dashboard route.
