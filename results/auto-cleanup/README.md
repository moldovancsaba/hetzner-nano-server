# Automatic cleanup verification

`initial-cleanup.json` records the first real apply run: one disposable alias created after bootstrap was removed, 16 existing protected models kept. The alias shared Qwen 0.6B blobs, so this proves safe deletion behavior, not a claim of physical disk recovery. Default/source model weights were preserved. The initial inventory history grace was retained across a subsequent gateway restart.

`public-verification.json` verifies that a tagged test did not update production-use metadata, the exclusive lease rejected new admissions, and normal service keys could not manage cleanup. Unit tests cover top-five union, 14-day cutoff, bootstrap, resident protection, durable usage/test exclusion, stale validation epochs, lease persistence across gateway restart and tracking failure behavior. No real production-use event was fabricated for this test.

The usage ledger and maintenance secret remain private on the server. Audit reports contain model identity/digest, keep/remove reasons and operation times only, not request bodies, outputs or user identities.
