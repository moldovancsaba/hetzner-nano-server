# Perplexity as the fallback search

When Brave's shared allowance is resting, a search task can still advance: the Search Coordinator reserves one Perplexity
request and runs the task's first query through the Perplexity Search API. Every result is a lead exactly like a Brave
result; the factory fetches each page itself and applies the same source, ownership and content checks before anything is
handed on.

- Limits: one request an hour, 24 a day and 744 a month, counted in the factory database before any network call
  (`perplexity.py`, pinned by `test_perplexity.py`). A reservation counts even when no response arrives.
- Off unless both are present: `"perplexity_enabled": true` in `factory.json` and the root-only secret
  `/etc/paperclip-perplexity.env` (`PERPLEXITY_SEARCH_API_KEY=...`, mode 600), read by `narimato-factory.service`.
  Without either, a resting Brave means the task waits, as before.
- Not served: source-only exchange projects, which keep Brave's country and language rules.
- Not a Brave replacement: Brave stays first. The Search API has no safe-search setting, so the factory's own page checks
  and the publication gates are the only filter on what a Perplexity lead leads to.
