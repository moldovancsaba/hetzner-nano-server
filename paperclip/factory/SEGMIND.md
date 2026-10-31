# Metered Segmind model lane

A paid, optional second model, used in two places: extraction by the **Research Analyst**, and (since 2026-10-30) the editorial-brief step of publication preparation, see [Editorial-brief choices](#editorial-brief-choices-2026-10-30). The local model (`granite4:1b-h`, 8K context) stays the default and is free. When its extraction leaves **name, address, price or opening hours** empty, the worker may ask a stronger model on Segmind to read a larger excerpt of the same public page. Status: deployed to the Paperclip host on 2026-10-29 and **switched on** by the owner the same day (`remote_llm.enabled: true` in `factory.json`, default limits). The dedicated API key is in `/etc/paperclip-segmind.env` (root-only, mode 0600). Backups of the pre-deployment files are in `/root/backups/factory-pre-segmind-20261029`. A six-entity pilot on stuck drafts is recorded in [segmind-pilot-20261029.md](segmind-pilot-20261029.md). A missing key, an exhausted allowance or any Segmind error simply leaves the local result in place.

Implementation: [segmind.py](segmind.py), tests [test_segmind.py](test_segmind.py). Background and cost estimates: `private/segmind-research-20261029.md` (not in Git).

## What it can and cannot do

- It can only **add** facts. Missing name, address, price or opening hours is what triggers the call (`segmind.TARGETS`); once called, it may add any of the seven research fields that are still empty, so the pilot also added activities, email and phone. It never replaces a fact the local model already established.
- Every value must carry a short quote that appears **verbatim** in the fetched page and contain the value (`worker.validate_facts`, the same gate the local model passes). A stronger model cannot introduce an invented fact; at worst it adds nothing. This protects against false facts, not against missed ones.
- The drafts remain drafts: human review, the quality reviewer and the publication gate are unchanged. The run comment states which fields the remote model added.

## What leaves the host

Only the **public source page** title and an excerpt (up to `max_input_chars`, default 24,000 characters) plus the fixed extraction instruction go to `https://api.segmind.com/v1/<model>`, which passes them on to the model's own provider. Never sent: support questions, customer messages, Paperclip comments or issue text, credentials, Camera/Habi/ClassScout user data. The code enforces the role: extraction is reachable only by `research` (`segmind.ROLES`) and the brief choice only by `publication` and `quality` (`segmind.BRIEF_ROLES`), so the **Support Drafter and Search Coordinator never call it**, and the Quality Reviewer and Publication Coordinator call it only through the brief step. **Owner decision, 2026-10-29:** Segmind's retention and training terms for text requests were not published on the pages reviewed that day, and the owner accepts that Segmind may use these requests for training. That is why the terms are not a gate. It is also why the data boundary above stays in the code: widening the role list is a separate decision.

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
- **Cost unit (calibrated 2026-10-29):** `x-cost` is in account credits, and one credit is one US dollar. A probe call of 143 input and 160 output tokens reported 0.000884 and moved the account balance by exactly that amount (117.9988016 to 117.9979175), which also equals the published per-million-token price. All cost limits are therefore dollars.
- **Fail closed:** HTTP 406 (no credits) pauses the lane for 24 hours; 429, 5xx, timeouts and other errors pause it for 5 to 15 minutes; 401/403 (key rejected) pause it until `segmind.py unblock`. Failed calls are not charged by Segmind. There is no retry loop.
- **Fixed origin**, no redirects, response size capped at 1 MiB, the API key only in the `x-api-key` header and never logged or placed in a prompt.

## Budget (owner's cap: $10 per month)

`factory.json` caps the lane at **$10 per month and $0.40 per day**, with call limits of 3,000 per month and 150 per day, so the dollar cap is what binds. The ledger counts only the factory's own calls: other spending on the same Segmind account is invisible to it, so the overspend guard below watches the account balance as a whole.

Measured on 2026-10-29 (24 real calls): $0.0030 on average and $0.0046 at most, for an average input of 6,600 characters; cost rises with page size, and a full 24,000-character page is estimated at $0.007. At those prices $10 buys about 3,300 average calls (110 a day), about 2,200 at the observed maximum (73 a day) and about 1,400 at the estimated worst case. The research role has run 94 to 121 tasks a day, so if most tasks escalate once, usage would be close to the cap; when the allowance is used up, research simply continues on the local model and says so in its run comment. Watch the first full month with `segmind.py status`.

## Weekly check and overspend guard (owner decision 2026-10-29)

- **Dashboard:** https://paperclip.haho.ai/factory has a **Segmind model spend** panel: this month and today against their caps, the last balance read from the Segmind account, the account's spend this month, the cooldown threshold, and the last five weeks with calls and spend. It reads the ledger and the last stored balance and never calls Segmind itself. Look at it once a week.
- **Guard:** before a call, and at most hourly, the lane reads the real Segmind balance (`GET /v1/get-user-credits`, read-only, no charge). Account spend for the month is the sum of the balance drops seen since the first reading of that month, so a top-up never offsets spending and other uses of the account count. The larger of that and the ledger's recorded cost is compared with **120% of `monthly_cost`** ($12.00 at the $10 cap). Past it the lane cools down until midnight on the first of the next month (Budapest) and research carries on with the local model; the run comment names the reason and the dashboard shows "Cooling down". The $0.40 daily cap is already a day's share of the month plus 20%.
- **If the balance cannot be read** the lane keeps working: the per-call ledger still bounds what the factory itself can spend.
- **Limits of the check:** the first reading of a month is its baseline, so spend before it is known only from the ledger. A Segmind top-up that happens between two readings can hide spending made in the same interval.
- **Hand tools:** `segmind.py watch` takes one reading now and applies the guard. `segmind.py unblock` lifts a cooldown, but the guard sets it again on the next call unless `monthly_cost` was raised first.

## Key rotation (deferred)

The API key was pasted into a chat on 2026-10-29. The owner deferred rotating it; it is tracked as [issue #1](https://github.com/moldovancsaba/hetzner-nano-server/issues/1) in the IDEABANK column of the repository's project board.

## Switching it on (owner action, needs an approved deploy)

1. In the Segmind console create a **dedicated API key** for the factory. Do not paste it into chat, an issue or Git.
2. On the Paperclip host, as root, write it without echoing it:

   ```bash
   install -m 0600 /dev/null /etc/paperclip-segmind.env && read -rs -p 'Segmind key: ' K && printf 'SEGMIND_API_KEY=%s\n' "$K" > /etc/paperclip-segmind.env && unset K
   ```

3. Deploy `segmind.py`, `worker.py`, `factory.json` and `narimato-factory.service` (which gains `EnvironmentFile=-/etc/paperclip-segmind.env`), then `systemctl daemon-reload && systemctl restart narimato-factory`. With `enabled` still `false` this changes no behaviour.
4. Calibrate: `segmind.py balance`, then `segmind.py probe` (one real call, a fraction of a cent), then `segmind.py balance` again. Check that the schema dialect was accepted and that `cost` in the probe output matches the balance change.
5. Set `"remote_llm": {"enabled": true, ...}` with limits in the calibrated unit. Run on the 27 `needs_more_evidence` entities first and compare accepted facts per unit of cost against the local result.

Run the CLI on the host **inside the service's own namespace and user, never as plain root**. The state directory is private to the unit: `/var/lib/private` is root-only, the files are stored as uid 65534 and the unit sees them as its dynamic uid. A root process, or a different uid, either cannot open the database or can leave root-owned `-wal`/`-shm` files that stop the worker. `nsenter` into the running service does it correctly:

```bash
set -a && . /etc/paperclip-segmind.env && set +a
PID=$(systemctl show -p MainPID --value narimato-factory)
nsenter -t $PID -m -S $(awk '/^Uid:/{print $2}' /proc/$PID/status) -G $(awk '/^Gid:/{print $2}' /proc/$PID/status) -- env PYTHONDONTWRITEBYTECODE=1 FACTORY_STATE=/var/lib/narimato-factory python3 /opt/narimato-factory/segmind.py status
```

Replace `status` with `balance` (read-only account call, does not open the database), `watch` (one balance reading and the overspend check), `probe` (one real call, recorded in the ledger) or `unblock`. The worker process itself only sees the key after the next `systemctl restart narimato-factory`.

## Editorial-brief choices (2026-10-30)

Owner decision 2026-10-30, after a delivery review: ready drafts were piling up (about 190 ready, 3 published) and 85% of the discovery drafts checked failed the editorial brief, the step that needs a publication name, borough, neighborhood, format and activity before a listing can be prepared. The lane was extended to that step; it is the only widening of the role list so far.

- **What it may do.** Choose *between values the pages already name*. ClassScout's own check (`publishing.normalize_sources`) requires the borough, neighborhood and activity to appear literally in the source text, so a model cannot make a missing word true. When the search hint is not on the page, or several canonical neighborhoods are, the model picks one from a candidate list built from the pages. Missing name, address or format wording, and a page that names no candidate at all, are never sent.
- **What is checked afterwards** (`growth.settle`, no model involved): the quote must be on the fetched pages, hold the chosen value and (for borough and neighborhood) the street address of this location; then the usual rules run again on the result: borough and activity named on the pages, the neighborhood in ClassScout's canonical list for that borough and named on the pages, and the Classes/Camps wording present. A choice that fails any check is dropped and the gap stands.
- **What is sent.** The public page excerpt, the drafted street address (a quoted public fact) and the candidate lists (borough names, ClassScout's public neighborhood list, the twelve activities). Nothing else.
- **Cost control.** One call per unchanged set of pages, address and candidates; the answer is stored with the draft (`commissioning_checks.result_json`, key `remote`) and reused after the hourly recheck. A failed or skipped call is not stored, so it is tried again later. The same ledger, daily and monthly caps and overspend guard apply.
- **Visibility.** The publication task says which fields the remote model chose. The queue report gives the first failed field for every draft that still has a gap (for example `Neighborhood is ambiguous: 2 Brooklyn neighborhoods are named (Carroll Gardens, Park Slope); a focused page is needed.`); the full list is `gaps` in the stored result.
- **Not covered.** Drafts that did not come from the discovery campaign carry no search hints and are skipped by this step (106 of the 193 ready drafts on 2026-10-30; an offline count found at most 25 of them could be settled by choosing, so the likely gain is small). Pages that name no neighborhood cannot be fixed by choosing.

### First run, 2026-10-30

Deployed 09:42 UTC (backup `/root/backups/factory-pre-brief-choice-20261030`), then run once over every ready discovery draft (87) with the new code, exactly as the queue would.

| | Before | After |
| --- | --- | --- |
| Complete editorial briefs (discovery drafts) | 12 (plus 1 exact catalog match) | 17 (plus 1) |
| Drafts the model was asked about | | 24 |
| Choices accepted after the checks | | 5 (all neighborhoods) |
| Choices dropped by the checks | | 2 |
| Asked, no usable choice returned | | 17 |

24 calls, $0.0642 in total, none failed; the month stood at 118 calls and $0.34 of the $10 cap. Reading the stored answers: four of the five accepted choices were right on the page (for example Queens Music Academy: Woodside, from the quote holding "60-19 Roosevelt Avenue, Woodside"). The fifth, "The Best of NYC: Gymnastics Classes", is a blog list rather than a provider, so the draft itself is the problem; the publication gate still has to hold it. The two dropped choices had addresses that were not street addresses ("Central Queens (Forest Hills)"). Most of the 17 empty answers were correct to abstain: a provider with an address in Lexington, MA; two addresses on one page; list pages naming a dozen neighborhoods. The first failed field for the 69 discovery drafts that still have a gap: neighborhood 36 (ambiguous or missing), borough 19, format wording 12, activity 2. This is not a controlled comparison and 87 drafts are a small sample; the briefs now flow into the existing publication gate, whose later checks (ages, schedule, price, contacts, media) are unchanged.


## Stop conditions

Disable the lane (`enabled: false`) if any private or customer text is found in a remote request, spending approaches the daily cap without a measurable gain in accepted facts, or the schema or cost probe fails.

## Not part of this change

LLM query planning for the Search Coordinator, Brave LLM Context/Places tests, Exa/Tavily comparison and any use of Gemini web-search grounding for discovery (Google's terms restrict using grounded results to choose pages to crawl). See the research note.
