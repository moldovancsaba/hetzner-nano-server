# Ranked model-policy deployment verification

The live HTTPS checks verify ranking-derived defaults, real explicit model selection, installed discovery, wrong-task rejection and shared-queue execution. They do not change model-quality scores.

At verification there were 18 installed packages, ten selectable for text and six selectable for Camera tasks. Other installed models remain visible but blocked for jobs without completed matching-digest evidence.

Current default job selections and result metadata were checked: Granite 4 1B Hybrid for text, LFM2-VL 450M Q8 for recognition, and LFM2.5-VL 450M Q8 for moderation. Explicit Qwen 0.6B and Qwen 1.7B requests returned those actual models, and explicit LFM2.5 recognition remained distinct from auto LFM2 recognition. Camera's human-review requirement remains unchanged.

The ignored local ClassScout env was configured with LOCAL_AI_MODEL=auto. No tracked ClassScout files or Vercel Production variables were modified. The shared gateway queue remains in memory and has the previously documented retention/restart limitations.
