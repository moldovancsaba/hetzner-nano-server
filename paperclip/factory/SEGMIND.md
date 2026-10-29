# Metered Segmind model lane

A paid, optional second model for the **Research Analyst** only. The local model (`granite4:1b-h`, 8K context) stays the default and is free. When its extraction leaves **price** or **opening hours** empty, the worker may ask a stronger model on Segmind to read a larger excerpt of the same public page. Status: deployed to the Paperclip host on 2026-10-29 with the flag **off** and no key installed (backups in `/root/backups/factory-pre-segmind-20261029`). The lane is **off** until the owner switches it on, and a missing key, an exhausted allowance or any Segmind error simply leaves the local result in place.

Implementation: [segmind.py](segmind.py), tests [test_segmind.py](test_segmind.py). Background and cost estimates: `private/segmind-research-20261029.md` (not in Git).

## What it can and cannot do

- It can only **add** a missing price or opening-hours fact. It never replaces a fact the local model already established.
- Every value must carry a short quote that appears **verbatim** in the fetched page and contain the value (`worker.validate_facts`, the same gate the local model passes). A stronger model cannot introduce an invented fact; at worst it adds nothing. This protects against false facts, not against missed ones.
- The drafts remain drafts: human review, the quality reviewer and the publication gate are unchanged. The run comment states which fields the remote model added.

## What leaves the host

Only the **public source page** title and an excerpt (up to `max_input_chars`, default 24,000 characters) plus the fixed extraction instruction go to `https://api.segmind.com/v1/<model>`, which passes them on to the model's own provider. Never sent: support questions, customer messages, Paperclip comments or issue text, credentials, Camera/Habi/ClassScout user data. The code enforces the role: only `research` can reach the lane (`segmind.ROLES`), so the **Support Drafter, Quality Reviewer, Publication Coordinator and Search Coordinator never call it**. Segmind's retention and training terms for text requests are **not published on the pages reviewed on 2026-10-29**; confirm them in the owner's Segmind terms before enabling, and do not widen the role list without that answer.

## Controls

All limits live in `factory.json` under `remote_llm`; values can tighten but never exceed the hard ceilings in `segmind.HARD`.

| Setting | Default | Hard ceiling |
| --- | --- | --- |
| `enabled` | `false` | must be `true` |
| `model` | `gemini-3.8-flash` | slug pattern only |
| `effort` | `low` | `low`/`medium`/`high` |
| `daily_calls` / `monthly_calls` | 40 / 600 | 200 / 3,000 |
| `daily_cost` / `monthly_cost` | 2.0 / 20.0 | 10 / 100 |
| `call_cost_ceiling` | 0.10 | 0.5 |
| `max_input_chars` | 24,000 | 60,000 |

- **Durable ledger** (`remote_llm_calls` in the factory SQLite, a restart cannot reset it). A call reserves its ceiling before it is sent; the real cost from Segmind's `x-cost` response header replaces it afterwards. A missing header or an unconfirmed (timed-out) call stays counted at the ceiling. Budapest day and month, like the Brave ledger.
- **Cost unit:** `x-cost` is documented but its unit is not. Treat the cost limits as being in that unit until `segmind.py balance` before and after `segmind.py probe` shows what one call costs against the account balance, then set the limits in dollars deliberately.
- **Fail closed:** HTTP 406 (no credits) pauses the lane for 24 hours; 429, 5xx, timeouts and other errors pause it for 5 to 15 minutes; 401/403 (key rejected) pause it until `segmind.py unblock`. Failed calls are not charged by Segmind. There is no retry loop.
- **Fixed origin**, no redirects, response size capped at 1 MiB, the API key only in the `x-api-key` header and never logged or placed in a prompt.

## Switching it on (owner action, needs an approved deploy)

1. In the Segmind console create a **dedicated API key** for the factory. Do not paste it into chat, an issue or Git.
2. On the Paperclip host, as root, write it without echoing it:

   ```bash
   install -m 0600 /dev/null /etc/paperclip-segmind.env && read -rs -p 'Segmind key: ' K && printf 'SEGMIND_API_KEY=%s\n' "$K" > /etc/paperclip-segmind.env && unset K
   ```

3. Deploy `segmind.py`, `worker.py`, `factory.json` and `narimato-factory.service` (which gains `EnvironmentFile=-/etc/paperclip-segmind.env`), then `systemctl daemon-reload && systemctl restart narimato-factory`. With `enabled` still `false` this changes no behaviour.
4. Calibrate: `segmind.py balance`, then `segmind.py probe` (one real call, a fraction of a cent), then `segmind.py balance` again. Check that the schema dialect was accepted and that `cost` in the probe output matches the balance change.
5. Set `"remote_llm": {"enabled": true, ...}` with limits in the calibrated unit. Run on the 27 `needs_more_evidence` entities first and compare accepted facts per unit of cost against the local result.

Run the CLI on the host **as the service user, never as root**. A root process that opens the live SQLite database can leave root-owned `-wal`/`-shm` files that the service (uid 65534) cannot write, which would stop the worker:

```bash
cd /opt/narimato-factory && set -a && . /etc/paperclip-segmind.env && set +a && setpriv --reuid=65534 --regid=65534 --clear-groups env PYTHONDONTWRITEBYTECODE=1 FACTORY_STATE=/var/lib/narimato-factory python3 segmind.py status
```

Replace `status` with `balance` (read-only account call, does not open the database), `probe` (one real call, recorded in the ledger) or `unblock`.

## Stop conditions

Disable the lane (`enabled: false`) if any private or customer text is found in a remote request, spending approaches the daily cap without a measurable gain in accepted facts, Segmind's terms turn out to permit training on submitted text, or the schema or cost probe fails.

## Not part of this change

LLM query planning for the Search Coordinator, Brave LLM Context/Places tests, Exa/Tavily comparison and any use of Gemini web-search grounding for discovery (Google's terms restrict using grounded results to choose pages to crawl). See the research note.
