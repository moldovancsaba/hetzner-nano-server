# Granite text-route correction

Active text assignment is now `granite4:1b-h`; the Camera vision model is unchanged. Mixed-workload verification checks correct model metadata, serialized execution, service permissions and compatible transport. Exact text-probe values are recorded separately in `semantic_text_probe`; a routing pass is not an accuracy pass.

The first replay of the old loose JSON prompt failed its exact-value assertion: Granite used a different key (`readySet`) instead of `ready`. This is an observed structured-answer limitation, not evidence that Qwen remained active. The verification now records this independent semantic check while checking routing and JSON transport separately; this does not alter any historical benchmark score. Use explicit schemas and validate expected fields for application tasks. See raw completion contents in the mixed verification artifact.

Pandora identity verification uses a real HTTPS login and chat request. Its response metadata reports Granite, and the page displays that actual model after a reply. Old chat messages can still contain Qwen self-descriptions; refresh/start a new conversation to clear them.
