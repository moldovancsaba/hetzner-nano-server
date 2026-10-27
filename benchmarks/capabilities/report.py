import json,statistics,pathlib
r=pathlib.Path(__file__).parent;d=json.loads((r/'results.json').read_text())
def f(v):return f'{v:.2f}' if isinstance(v,(int,float)) else '—'
def score(ts):return f"{sum(t['passed'] for t in ts)}/{len(ts)}" if ts else 'not applicable'
lines=['# Model capability benchmark — measured on our Hetzner server','',
'Hardware: CAX11, 2 shared ARM64 vCPUs, 4 GB RAM, no GPU. Ollama container kept at 2 CPUs / 2800 MiB; context 2048. Two repeats per case; small controlled sample, not a production accuracy estimate.','',
'## Results','',
'| Model | Listings (4 cases ×2) | Query plan ×2 | OSM facts ×2 | Injection resistance ×2 | Native tool call | Valid JSON* | Median request seconds | Peak container MiB |',
'| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
for m in d['models']:
 ts=m['tests'];listing=[t for t in ts if t['name'].startswith('listing_')];plan=[t for t in ts if t['name']=='query_plan'];osm=[t for t in ts if t['name']=='osm_facts'];inj=[t for t in ts if t['name']=='prompt_injection'];js=[t for t in ts if t.get('json_valid') is not None];lat=[t['seconds'] for t in ts if t['ok']];tool=m.get('native_tool_call')
 lines.append('| '+' | '.join([m['model'],score(listing),score(plan),score(osm),score(inj),('pass' if tool['passed'] else 'fail') if tool else 'not tested',f"{sum(t['json_valid'] for t in js)}/{len(js)}" if js else '—',f(statistics.median(lat)) if lat else '—',f(m.get('peak_container_memory_mib'))])+' |')
lines+=['','*JSON constraint was enabled for structured tests. Valid syntax does not imply correct facts. Median mixes short and longer cases; compare case-level data for task latency. Memory includes container file cache and runtime overhead; it is not model RSS.','',
'## Switching and loading','',
'| Target | Unload endpoint seconds (range) | Ollama load seconds (range) | First short response seconds (range) |','| --- | --- | --- | --- |']
for m in d['models']:
 ts=[x for x in d['switch_trials'] if x['to']==m['model']];u=[t['unload_seconds'] for t in ts];ld=[t['first_response']['load_seconds'] for t in ts if t['first_response']['ok']];fr=[t['first_response']['seconds'] for t in ts if t['first_response']['ok']]
 def span(xs):return f'{min(xs):.3f}–{max(xs):.3f}' if xs else 'failed'
 lines.append(f"| {m['model']} | {span(u)} | {span(ld)} | {span(fr)} |")
lines+=['','Trial one switches from the previous model; trial two unloads/reloads the same model. Downloaded files may be OS-cached. Unload request latency does not establish exactly when every RAM page was reclaimed. First response includes load, prompt processing and generation.','',
'## Vision','']
for m in d['models']:
 if 'vision' in m.get('capabilities',[]):
  lines.append(f"### {m['model']}")
  for t in m['tests']:lines.append(f"- {t['name']} trial {t['trial']}: {'PASS' if t['passed'] else 'FAIL'}, {t['seconds']:.2f}s; response: `{t.get('response','')}`"+(f"; error: {t.get('error')}" if not t['ok'] else ''))
lines+=['','Other tested tags report no vision capability; Gemma 3 1B is text-only even though larger members of its family support images. Test photo: two cats on a pink surface; source and method in README.md. One photo cannot establish general image accuracy, OCR, venue recognition, or object-count reliability.','',
'## Failures retained','']
for m in d['models']:
 for t in m['tests']:
  if not t['passed']:lines.append(f"- **{m['model']} / {t['name']} / trial {t['trial']}**: `{t.get('response','')}`"+(f" Error: {t.get('error')}" if not t['ok'] else ''))
 t=m.get('native_tool_call')
 if t and not t['passed']:lines.append(f"- **{m['model']} native tool call**: {t.get('error') or json.dumps(t.get('tool_calls'))}")
lines+=['','## Integration boundaries','',
'Atlas connection was read-only from the owner’s Mac with existing credentials, an indexed projection and eight-record limit. Only public fields were copied to Hetzner. Selection tests rank those live records. Native function arguments were tested separately. See live-atlas-tool-result.json for the additional validated tool → real Atlas query → model recommendation check when present. No Atlas write, broad scan, or unrestricted model-generated query was executed. Hetzner-to-Atlas connectivity and production ClassScout integration are not proven by this run.','',
'OSM facts came from one real, cached Nominatim lookup. Models were given the returned data; they did not browse autonomously. Coordinates/website and refusal to invent missing ticket price were checked. OSM data can be stale; successful extraction does not independently verify current venue facts. Attribution: © OpenStreetMap contributors, ODbL. Follow https://operations.osmfoundation.org/policies/nominatim/ for public-service use.','',
'Prompt injection is a real blocker to trusting untrusted text. Even a model passing this single case is not secure in general. Build allowlisted, read-only tools, deterministic hard filters, schema validation, and returned-ID verification outside the model. Do not store credentials in prompts.','',
'## Runtime restoration','',f"Original model reload: {json.dumps(d.get('restored_original'))}",'',
'No application model setting or public route was switched by this benchmark. Candidate models remain on disk for future evaluation; only one is configured to be loaded at once.']
(r/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(str(r/'REPORT.md'))
