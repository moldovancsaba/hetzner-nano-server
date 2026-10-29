# ClassScout review handoff — initial batch

This document records the initial batch review packets. The later [publication workflow](PUBLISHING.md) adds actual delivery for complete, human-approved new class listings.

The factory prepares research proposals. ClassScout remains the source of truth for its public catalog, schema, duplicate rules and publication gates.

## Verified receiving interface

The existing `https://getyourfield.com/api/ingest` capability endpoint accepted the existing ClassScout credential and returned HTTP 200 during this work. Credentials remain in ClassScout's ignored local environment; none were copied into Paperclip or its model context. The provider patch envelope is:

```json
{"operations":[{"resource":"provider","action":"patch","id":"existing-provider-id","patch":{"phone":"source-supported value"}}]}
```

This is a contract example, not a submitted change. The receiving handler is `src/app/api/ingest/route.ts`; validation and writes run through `src/lib/ingestOperations.ts`, the canonical `curatedProviderSchema`, claimed-listing protections and serving projection hooks. The old handover document understates current capabilities; current code also supports bounded catalog reads through the intake API.

## Prepared review packets

`classscout_handoff.py` combines exported batch evidence with a bounded read-only catalog snapshot and writes `classscout-handoff-20261028.json`. It generates review packets, not publication approval. It never writes the catalog or enables a schedule.

- Existing listings are flagged for improvement rather than duplicated.
- Only a missing phone or email can become a proposed `provider.patch` operation. Matching contacts are no-ops; different nonempty contacts require conflict review.
- The West Side YMCA match is a summer-camp record. Its camp contact cannot be replaced with a general branch contact, even when the street location matches.
- Claimed records are held for their existing owner workflow.
- New providers require confirmed location identity, the complete canonical schema, child age/program evidence, public copy, an accepted image and existing publication checks. A seven-field extraction is not a complete provider document.
- Facility hours do not become class schedules. Unknown price does not become free. Source quotations do not become public descriptions.

Example invocation on the operator workstation:

```sh
python3 paperclip/factory/classscout_handoff.py \
  --batch paperclip/factory/batch-20261028.json \
  --catalog private/paperclip/catalog-match-20261028.json \
  --output paperclip/factory/classscout-handoff-20261028.json
```

The catalog snapshot is private and excluded from Git. Exported batch facts describe public businesses and retain source URLs, retrieval dates, quotes and hashes. Keep failed attempts and rework linked; a successful retry does not erase the initial failure.

## Approval and next action

Review the summary in Paperclip NAR-11 and the handoff findings in NAR-2. Existing contacts that already agree need no write. Resolve program scope, missing evidence and full-schema requirements before submitting any proposed operation through the existing ClassScout content workflow. Actual live publishing and recurring operation remain unenabled by this handoff. No ClassScout application code, production configuration or catalog record was changed.
