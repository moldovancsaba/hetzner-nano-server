# Local model selection for Narimato Paperclip

Decision date: 2026-10-27 (Europe/Budapest). This selects the model and initial worker design; context acceptance testing is now recorded separately. The bounded [source-page factory](factory/README.md) is deployed for a ClassScout pilot.

## Decision

Select IBM Granite 4 1B Hybrid, Ollama ID `granite4:1b-h`, as the initial local inference model for bounded English content research and support assistance. It is the strongest measured candidate on our current hardware for short structured tasks. No existing evaluation certifies an autonomous CEO or the complete company operating plan.

Keep inference on the existing narimato-chatbot server and Paperclip orchestration/tools on narimato-paperclip. This uses the two existing hosts without adding a second inference process to Paperclip's 4 GB machine. It shares the chatbot server's queue/capacity; it does not provide dedicated model throughput. A separately authenticated Paperclip tenant is now provisioned; do not reuse ClassScout, Habigoal, Camera or Pandora keys. Its tested total context is 8192 tokens. See the context evidence in ../benchmarks/paperclip-context/.

## Evidence and limits

The canonical English structured-task ranking gives Granite 14/14 correct, 14/14 valid JSON, a passing native tool-call check and a 3.03-second descriptive median. Qwen3 1.7B and 0.6B each scored 12/14; the small dataset does not establish a general intelligence ranking. These are short model calls on an ARM CPU, not end-to-end internet research times. See ../benchmarks/rankings/ENGLISH.md, ../benchmarks/round3/REPORT.md and ../docs/MODEL-POLICY.md.

Earlier prompt-injection checks failed for all six candidates in that round; Granite 4 was not among those original six. This provides no evidence that Granite is injection-resistant. Our non-English evaluation approves no production language-specific workflow. Hungarian support needs separate testing and fluent review.

Read-only Paperclip host inspection on this date: 2 vCPUs, 3.7 GiB physical RAM, approximately 1.057 GiB current Paperclip container use, 2.1 GiB Linux available memory and 2 GiB unused swap. These are snapshots, not peak capacity measurements. Paperclip's container limit is 2800 MiB. Loading a larger model alongside growing Paperclip/agent/browser workloads lacks demonstrated headroom.

Default chatbot consumers now also use the verified 8192-token Granite profile; explicitly selected alternatives retain their original limits. Paperclip has a separately validated 8192-token context and at most 1024 output tokens, with tokenizer-based admission, a template reserve, 32 messages and eight tool definitions. Long Paperclip calls use async jobs. Do not feed the whole company plan or an unrestricted agent instruction bundle into this profile. The Paperclip gateway profile now checks the verified Granite tokenizer and rejects over-budget input rather than allowing silent truncation.

## Internet, research and support

A model does not fetch the internet itself. Use a small Paperclip process/HTTP worker with fixed tools and bounded steps:

1. Search using an explicitly configured search service, feed or authoritative directory API. The owner selected source-page research for the initial ClassScout pilot. No search provider is configured; fetching supplied URLs does not provide broad discovery.
2. Fetch public source pages with time/size/redirect limits and protection against private-network destinations. Extract compact passages and store URL, retrieval time and evidence outside the model context. Use an isolated browser only for pages that require it; its capacity remains unmeasured.
3. Give Granite one narrow extraction, classification, supported summary or support-draft task at a time. Represent missing facts explicitly and retain field-level source evidence.
4. Apply deterministic schema, duplicate, identifier and provenance checks. Return draft listings/corrections and support drafts to Paperclip with unresolved questions. A model assertion is not proof that a source was fetched or an action executed.
5. Initially process one job at a time with bounded retries and a step limit. Measure completed accepted records, factual errors, failures and end-to-end time.

Keep source text separate from operator instructions. Permissions and tool execution must be enforced by application code, not prompt wording. Begin with read-only access and draft output. The supplied plan reserves external communication, spending, contractual decisions and high-impact actions for appropriate authority; this selection does not authorize them.

## Mapping the supplied operations plan

Phase 1 content operations is the appropriate pilot: discovery from approved sources, field enrichment, freshness checks, duplicate suggestions and draft corrections. Support should answer from approved documentation and verified listing data and escalate unsupported questions. Free-form autonomous commercial strategy, negotiations, publishing, finance and company-wide management are not approved capabilities of this model.

Use separate task types and persistent records for each brand. A shared model may serve many logical specialist roles sequentially; additional agent names do not create additional reasoning capability or compute capacity. Keep long-term company state in Paperclip and the entity registry rather than a growing conversation.

## Acceptance before enabling an agent

Build a realistic Phase 1 evaluation with actual fetched evidence: discovered listing extraction, missing contact/pricing fields, conflicting sources, stale/closed businesses, duplicate suggestions, unsupported support questions, source citations and malicious source instructions. Verify real tool execution and Paperclip task/result persistence, bound tool permissions, and confirm that failures become visible review items. Record factual support independently from JSON validity. The live source-page pilot verifies real Paperclip execution, source fetching, extraction, persistent quotes and human-review handoff. It does not establish broad discovery, conflict resolution, stale-business detection or general research autonomy; those cases remain a separate acceptance backlog.

The stock OpenCode adapter is not a drop-in choice for the current gateway profile. Ollama's current OpenCode guide recommends/requires 64k-plus context, above the validated 8192-token default text profiles, and its own web-fetch capability still needs a functioning tool loop. Use a compact worker for the pilot, or evaluate a separate larger-context deployment before choosing OpenCode. Do not raise the shared production context without measuring memory, latency and existing-client effects.

## Upstream checks

- IBM model card, capabilities and tool schema: https://huggingface.co/ibm-granite/granite-4.0-h-1b
- Exact Ollama tag: https://ollama.com/library/granite4:1b-h
- OpenCode integration/context guidance: https://docs.ollama.com/integrations/opencode
- Paperclip adapter architecture: https://github.com/paperclipai/paperclip/blob/master/doc/ADAPTERS.md

Newer small models, including Qwen3.5 variants, are evaluation candidates, not measured winners for our workloads. Choosing them from model-family claims alone would not justify replacing the tested selection.
