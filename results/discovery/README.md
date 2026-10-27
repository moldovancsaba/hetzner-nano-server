# Discovery deployment evidence

The initial report is a public-metadata snapshot, not an assertion that candidates work locally. It records source responses/status/hashes, model metadata, prior-evidence matching, heuristic scores and limitations. Final scope filtering produced 24 candidates from 658 source/model records; all 12 feeds succeeded. The metadata service never downloaded weights or generated responses.

The actual ongoing reports are in the restricted `/var/lib/narimato-model-discovery` state directory on Hetzner. This GitHub file is a dated snapshot, not an automatically refreshed web feed. Timer state and first-run service verification are recorded separately.
