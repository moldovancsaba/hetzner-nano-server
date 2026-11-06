# Racket Land connection

Racket Land replaces Padel Africa at https://racket.land. The authenticated application declares the canonical vertical `racket-land`, worldwide `unrestricted` territory and racket-sport discovery vocabulary. Its taxonomy uses `racket-club`; the application accepts its old category alias. The native transport scope, project ID, scoped credentials, receipt tables, packet IDs and original operations retain their existing `padel-africa` identity. Renaming those durable identities would strand uncertain requests and is a separate migration.

The native engine and evidence-intake clients use the new origin and verify the new application identity and explicit worldwide policy. Source pages need a sport word declared by that authenticated policy. A venue's own supported city and country determine location; the finite discovery-locality list is search intent and cannot restrict worldwide admission. Existing ownership, exact street, duplicate, bounded evidence and destination handoff gates still apply. Unknown countries remain held. Country names and valid codes use the bundled public IANA/Intl registry with its provenance; existing application aliases are preserved.

The existing native search lane reads that application vocabulary before searching and uses it to screen independently fetched pages. It does not create a replacement account, schedule, search allowance, source identity or destination grant. Existing `padel` workflow names remain compatibility identifiers, not a restriction to that sport. Sportolok continues to use its own country and language policy.

## Status, 2026-11-06: repository only

Nothing in this document is deployed to the Paperclip host, and the repository does not match the host. According to the earlier session's record (not re-checked here), the host runs the delivery code of 2026-11-01, which exists only as uncommitted changes in the owner's original checkout (among them `brave.py`, `search_workflow.py` and `worker.py`). Commit 3c42953 and the commits after it on branch `racket-land-worldwide` have not been applied there. The test results below are repository results.

## Plain pages, worldwide

A page without structured data qualifies as before: one owned name, one street, one country. For the `unrestricted` scope (`factory/venue_identity.py`):

- **Country.** Every registry name and legacy alias in `racket_countries.json` is matched with word boundaries; the longest name wins, so "Equatorial Guinea" is not also "Guinea". Names that are also common place or personal names (Georgia, Jordan, Chad, Jersey, Lebanon, Mexico, Ireland, Jamaica, Panama, Peru, Turkey) count only as the last part of a line, as in "Amman, Jordan". Exactly one country must remain. Abbreviations that the registry does not hold ("USA", "UK", "UAE") name no country, so a page that uses only those stays held until the application's alias list covers them.
- **City.** The city is the component right after the street on the same line (`123 Main Street, Austin, TX 78701, United States`), unit parts such as `Suite 4` skipped. A prose address, a region code, a country name or two different readings give no city. When none can be read, the page is taken only if exactly one declared discovery locality is written on it, otherwise it stays held; the list never decides whether a venue is admitted and no city is invented.
- **Other verticals.** The continent and countries scopes (the legacy `padel-africa` slug and Sportolok) keep their fixed country dictionary and still take the city only from a single declared locality. Their plain-page results are unchanged.

## Directories and link patterns

`provider_host` refuses the older `DENIED` substrings and the whole domains in `DENIED_DOMAINS` (`matchi.se`, `playbypoint.com`, `courtreserve.com`, `clubspark.lta.org.uk`, `tennis.com`, `squashlevels.com`, `pickleheads.com`), each with its reason. The new entries are matched as a domain or subdomain, never as a substring, because a venue host such as `northshoretennis.com` contains `tennis.com`. Governing bodies (`badmintonengland.co.uk`, `lta.org.uk`, national federations) were left out: they can run venues of their own, and a directory page that lists several venues is already held by the one-venue rule. `playtomic.com` was not added because its use as a venue-hosting domain was not confirmed.

For `racket-land` the link patterns in `resolve` and `branch_links` are built from the authenticated `requiredTopicWords` (host and `/pages/` names), generic venue words and the declared localities (path hints only). The earlier fixed patterns stay for every other vertical.

## Native search lane: what must change once the delivery code is committed

`brave.py`, `search_workflow.py` and `worker.py` carry uncommitted host work and were not edited. In the committed copies, the Brave locale for the `padel` kind is `('ZA','en')` (`search_workflow.py`, the `locale=` expression in `run`), `brave.py` accepts only `('US','en')`, `('ZA','en')` and `('HU','hu')`, and `source_projects.py` accepts only `('US','en')`, `('ZA','en')` and `('ALL','hu')`. Racket Land searches are therefore biased to South Africa and English. The host copies were not read here and may differ.

Proposed patch, to be written against the committed delivery code:

1. Locale for the `padel` kind: country `ALL` (no country bias) unless the queued locality has a known country, in which case that country code; language from the vertical's declared `locales`: the locality country's language when it is listed, otherwise `en`. Sportolok (`HU`, `hu`) and ClassScout (`US`, `en`) are unchanged.
2. `brave.py`: replace the three-pair allowlist with a check that the country is `ALL` or a two-letter registry code and the language is a two-letter code from a short reviewed list, so a typo still fails closed and an unreviewed pair is still refused.
3. `source_projects.py`: accept the same checked pairs in a reviewed source plan, keeping the review reference, query bounds and interval rules.
4. Tests in `test_search.py` and `test_source_projects.py` for the new pairs and for the pairs that must still be refused. Check that the locale is part of the seven-day deduplication key, otherwise a changed locale reuses an old result.

## Release and recovery

Use `ops/deploy_factory.py --racket-land-runtime --runtime-digests /absolute/private/digests.json`. The private digest file names the host's current engine_ops.py, padel.py, venue_identity.py, search_workflow.py, source_exchange.py and the two support files; missing support files are null and existing files require their exact digest. Only the operator can produce it, from the host. The repository half is `ops/racket_runtime_patches.json`: exact before and after text for engine_ops.py, padel.py, venue_identity.py and search_workflow.py, applied to the host files so that unrelated current native work is preserved. On 2026-11-06 its rows for the first three files were rebuilt as the full difference from the parent of 3c42953 to the current files (they now also carry the plain-page, link-pattern and copy changes). They assume the host files equal that parent, as the earlier rows did; a host file that differs, or one that already holds the earlier 3c42953 rows, is refused. The original source-exchange module is unchanged. `dashboard.html`, `workflows_setup.py`, `provision.py` and the React dashboard are not part of this mode and need their own release.

The helper defaults to a read-only plan. Applying requires the existing verified idle pidfd stop, consistent private backup, exact source/configuration comparisons and healthy restart. A busy process is preserved. Readiness failure restores prior code without overwriting newer business or receipt databases. No manual business task or paid search is part of verification. After release, inspect the read-only authenticated application catalog through the installed client and verify service health and unchanged configuration. Natural source outcomes are measured separately; passing a connection check does not establish a published listing.

For rollback, restore the captured code and support files only under the same idle/recovery protocol. The former Africa-only code will hold against the new application identity; it must not silently reinterpret worldwide sources as African sources. Preserve all original requests, source credentials, writer fences and receipt history.
