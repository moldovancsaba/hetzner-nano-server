# Evidence files

Historical setup measurements are described in ../docs/MEASUREMENT.md. Files here capture a later check on 2026-10-26; UTC timestamps are used in machine-readable benchmarks.

- benchmark-20261026T192229Z.json: five synthetic requests, 3/5 strict passes, all HTTP 200 and valid JSON. Read the limitations before interpreting this as accuracy.
- health-classscout-2026-10-26.json and health-habigoal-2026-10-26.json: missing and invalid keys rejected; intended key accepted.
- server-status-2026-10-26.txt: memory, CPU, disk, service, firewall snapshot.
- versions-and-listeners-2026-10-26.txt: actual OS/runtime versions, model ID and network listeners.

Do not edit failed results to make them pass. New runs create new timestamped files. Never save real API keys, headers, private prompts or personal data here.
