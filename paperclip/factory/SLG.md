# Sales Lead Generator connector

The SLG connector uses the app's existing fixed-origin HTTP JSON-RPC endpoint:
https://salesleadgenerator.vercel.app/api/mcp . The server specification and
`tools/list` are public. Execution requires an explicit configured workspace and a
brand-scoped `slg_…` API key. Never infer a workspace from an omitted field: SLG's
server otherwise defaults to `cogmap`.

## Current operating boundary

The owner requested partner management and sales communication. The connector is
prepared for activation; the intended service/workspace and a scoped credential
have been requested. Those are required inputs, not inferred from the app's sample
workspace names. No live lead data has been read or modified during commissioning.
No message has been sent. Existing customer-support replies remain drafts.

The six live tools are:

| Tool | Use | Paperclip boundary |
| --- | --- | --- |
| slg_search_leads | Bounded pipeline selection | At most 20 per stage; samples are labelled |
| slg_get_lead | Exact partner record | Exact 24-character ID and workspace |
| slg_get_pre_call_briefing | Internal sales preparation | Stored CRM facts, not independent verification |
| slg_list_pipeline_stages | Stage guidance and connection check | Authenticated read |
| slg_capture_lead | Deduplicated CRM capture/update | Durable guarded path; disabled pending configuration |
| slg_update_lead_stage | Explicit stage change | Durable guarded path; never implies email sent or revenue won |

After the owner confirms the service/workspace and saves its scoped key, run
`python3 paperclip/configure-slg.py --brand WORKSPACE --key-file private/slg-api-key.txt`
from the Hetzner project. It verifies authenticated stage guidance first, installs
the key through encrypted stdin, preserves existing workspaces, registers the
manual workflows and commissions connection/pipeline reads. CRM writes and
sending stay disabled. Wait for current factory work to finish if refused.

Native manual workflows are connection check, pipeline review and exact-lead
briefing. Register them when `sales.brands` contains the confirmed workspace(s).
The existing Operations role handles these without a new model, inference or
Brave allowance. Do not enable recurring sales campaigns without a confirmed
service, target audience, sender and cadence.

Every RPC call uses POST, so the current SLG authorization implementation requires
`read-write` scope even for read tools. Paperclip restricts the read path locally.
Use a separate revocable key per workspace rather than the shared legacy key.
The restricted server `/etc/paperclip-slg.env` defines `SLG_SCOPED_KEYS` as a JSON map of workspace slug to
raw scoped key. The service manager loads it into the restricted worker environment. It is not placed in `factory.json`, task descriptions, output or
logs. Local input may be saved at `private/slg-api-key.txt` for installation and
should be kept private. Backup bundles include the installed credential file.

`factory.json` initially has `sales.brands=[]`, `crm_writes_enabled=false` and
`delivery_enabled=false`. `provision.py` preserves this configuration. Unknown or
cross-workspace requests fail before transport. CRM mutations retain durable
request/receipt state and confirm the resulting record. Lost/invalid receipts or
failed readback become uncertain and stop replay, including across different
packets for the same record. There is no automatic mass capture or stage movement.

## Communication is a separate integration

None of these six tools sends email, reads a conversation, writes a draft or
manages a follow-up cadence. The application separately implements
`POST /api/outreach-send`, its cadence runner and per-lead activity history. The
send route uses the stored lead contact, a brand sender and a client idempotency
key; its mail service checks suppression. Session-bound personal Gmail differs
from scoped-key machine sending, which relies on the application's Resend
configuration. A successful public tools/list does not prove any sender works.

Before enabling automated sales delivery, confirm the service/workspace, target
segment, exact offer and sender/reply address; inspect the configured brand and
mailbox; connect incoming replies/activity and suppression to stop follow-ups;
then verify a controlled owner-address send and its receipt before any prospect
campaign. Preserve the original message/thread identifiers and never call an
outreach log a sent message. No network send path is exposed by this initial
Paperclip connector. LinkedIn delivery is not supplied by this MCP catalog.

## Capture caveats observed in the app source

The server capture implementation defaults missing country to HU and missing
contact identity/role to placeholders with decision-maker flags. It also creates
sports/entertainment industry metadata. Do not use those defaults as researched
facts or assume this is a generic catalog-provider import. Paperclip requires
explicit source URL, organization, actual named decision maker, role, locality
and buying role in its capture arguments; CRM writes remain disabled pending the
chosen business scope. Existing OpenClaw discovery/enrichment jobs retain their
ownership and are untouched.

## Verification

Generated acceptance metadata is in `slg-acceptance-20261028.json`. Controlled
checks cover workspace isolation, exact IDs, read bounds, contract errors, missing
capture facts, stage reasons, read-path mutation refusal, credential gating,
readback, idempotence and no replay after a lost write reply. The live public
specification and RPC list returned all six tools; unauthenticated tool execution
was refused with HTTP 401. Tests do not send messages, create fake CRM records or
spend model/search allowance. App source was read without editing or deploying SLG.
