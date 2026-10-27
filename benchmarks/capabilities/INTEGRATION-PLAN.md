# How the tested capabilities should become product features

## Atlas recommendation

Browser -> authenticated ClassScout endpoint -> validate intent/filter JSON -> bounded indexed MongoDB serving query -> apply hard constraints in code -> pass a small candidate set to the model -> validate returned IDs/schema -> render listing cards from database values.

The model is not a MongoDB client. Use a narrowly scoped application tool and a database user with only the required reads. Do not execute arbitrary model-generated MongoDB operators, Javascript, aggregation stages or connection strings. Apply city/visibility/price limits in the query and backend, not just the prompt. Copy names/addresses/prices from canonical records after model selection. Unknown price is not zero. Reject IDs outside returned candidates. Trace tool timings separately from model timings.

Tool-calling support is optional: a validated JSON filter plan can drive the same fixed query builder. Even native tool calls require identical validation. Untrusted listing descriptions must never authorize actions or change tools. A passing injection test does not grant trust.

## OpenStreetMap venue facts

Browser -> validated venue-name/city request -> provider-specific lookup adapter -> cached result with source ID and timestamp -> model extracts or explains supported facts -> schema check -> deterministic field/source validation.

Prefer showing name, address, coordinates, website and OSM attribution directly from returned data. Use the model for wording or intent interpretation. Missing opening hours, price, phone or accessibility are unknown, not invented. OSM may be incomplete or stale. Public Nominatim requires intentional provider choice, an identifying User-Agent, caching, at most 1 request/second across the application, proper attribution, no autocomplete/bulk systematic scans, and no personal data; see its current policy. Production traffic should use an appropriately provisioned provider rather than assuming the public endpoint is unlimited.

## Image understanding

Browser -> authenticated upload endpoint -> validate actual image type, pixel dimensions and payload size -> resize under a defined limit -> dedicated vision model -> validate expected output -> return caption/attributes and uncertainty.

Text-only models cannot be given image understanding by passing filenames or URLs in text. A real vision-capable model must receive decoded image content through its supported API. Keep image uploads and logs private, define deletion/retention, and do not treat model OCR/counts/identity claims as certain. Swapping vision and text on one tiny server affects first-response time and both projects; serialize work or use separate capacity if demand justifies it.

No image upload endpoint or Atlas/OSM production tool was added to Pandora by this benchmark. Results establish feasibility of bounded test flows, not a finished application integration.
