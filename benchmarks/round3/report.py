"""Builds round 3 rankings.json and REPORT.md. Reads results.json, results-extra.json, reasoning-check.json (if present) and earlier results from ../capabilities and ../round2.
Ranks English models on the 14 shared checks and image models on five schema-constrained cases, lists outcomes and failures, and prepends CONCLUSIONS.md if present."""
import pathlib,json,statistics,datetime
ROOT=pathlib.Path(__file__).parent;BASE=ROOT.parent
main=json.loads((ROOT/'results.json').read_text());extra=json.loads((ROOT/'results-extra.json').read_text()) if (ROOT/'results-extra.json').exists() else {'text':[],'vision':[]}
def pretty(s):
 for prefix in ['hf.co/LiquidAI/','hf.co/ggml-org/','hf.co/QuantFactory/']:s=s.replace(prefix,'')
 return s.replace('-Instruct-GGUF:Q4_K_M',' Q4').replace('-Instruct-GGUF:Q8_0',' Q8').replace('-GGUF:Q4_K_M',' Q4').replace('-GGUF:Q8_0',' Q8')
def score(ts):return f"{sum(bool(t.get('passed')) for t in ts)}/{len(ts)}" if ts else 'not run'
def med(ts):
 xs=[t['seconds'] for t in ts if t.get('ok')];return round(statistics.median(xs),3) if xs else None
def fmt(n):return f'{n:.2f}' if isinstance(n,(int,float)) else '—'
common={'listing_soccer','listing_swimming','listing_no_match','listing_unknown_price','query_plan','osm_facts','prompt_injection'}
# Only the shared fourteen English checks enter this leaderboard.
text={}
for m in json.loads((BASE/'capabilities/results.json').read_text())['models']:
 if 'vision' not in m.get('capabilities',[]):text[m['model']]=m
for m in json.loads((BASE/'round2/english-results.json').read_text())['models']:
 if m.get('tests'):text[m['model']]=m
for m in main['text']+extra['text']:
 if len([t for t in m['tests'] if t['name'] in common])==14:text[m['model']]=m
ranked=[];budget_limited=[]
for name,m in text.items():
 ts=[t for t in m['tests'] if t['name'] in common]
 if len(ts)!=14:continue
 empty_length=sum(t.get('done_reason')=='length' and not t.get('response','').strip() for t in ts)
 if 'thinking' in m.get('capabilities',[]) and empty_length>len(ts)/2:
  budget_limited.append({'model':name,'empty_length_limited_cases':empty_length,'total':len(ts)});continue
 tool=m.get('tool_call',m.get('native_tool_call',{}))
 ranked.append({'model':name,'passed':sum(t['passed'] for t in ts),'total':14,'json_valid':sum(t['json_valid'] for t in ts),'native_tool_passed':bool(tool.get('passed')),'median_seconds':med(ts)})
ranked.sort(key=lambda x:(-x['passed'],-x['json_valid'],-x['native_tool_passed'],x['median_seconds']))
# Image ranking uses the five schema-constrained cases independently of English scores.
r2=json.loads((BASE/'round2/results.json').read_text());r2retry=json.loads((BASE/'round2/vision-retries.json').read_text());r2schema=json.loads((BASE/'round2/schema-vision.json').read_text())
vision=[]
def vr(name,size,tests,raw,first):
 return {'model':name,'schema_passed':sum(t.get('passed') and t.get('keys_match',True) for t in tests),'schema_total':len(tests),'max_image_dimension':size,'raw_passed':sum(t['passed'] for t in raw),'raw_total':len(raw),'first_photo_seconds':first,'first_poster_seconds':next((t['seconds'] for t in raw if t['name']=='poster_ocr' and t.get('trial')==1),None),'tests':tests}
for m in r2schema['models']:
 raw=next((x for x in r2retry['models'] if x['model']==m['model'] and x.get('status')=='ran'),None)
 if raw is None:raw=next(x for x in r2['vision'] if x['model']==m['model'])
 vision.append(vr(m['model'],m['max_image_dimension'],m['tests'],raw['tests'],raw.get('first_image',{}).get('seconds')))
for m in main['vision']+extra['vision']:
 tests=m.get('schema_tests',[])
 if len(tests)!=5:continue
 first=next((x['seconds'] for x in m.get('image_attempts',[]) if x.get('ok')),None)
 vision.append(vr(m['model'],m['max_image_dimension'],tests,m['tests'],first))
def unique_time(m):
 ts=[m[k] for k in ['first_photo_seconds','first_poster_seconds'] if m[k] is not None];return statistics.mean(ts) if ts else float('inf')
vision.sort(key=lambda x:(-x['schema_passed'],-x['max_image_dimension'],unique_time(x)))
output={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Measured on our 4 GB CPU server; separate English and image model-variant rankings','english_policy':'Common 14 checks only; correctness, JSON validity, native tool call, then median latency. Non-English excluded.','english':ranked,'english_budget_limited':budget_limited,'image_policy':'Same five schema checks; within equal counts use tested image resolution then mean first-photo/first-poster time. Small sample, descriptive ordering.','image':[{k:v for k,v in m.items() if k!='tests'} for m in vision]}
(ROOT/'rankings.json').write_text(json.dumps(output,indent=2)+'\n')
lines=['# Additional candidates: English and image analytics','',
'Tested on the existing 4 GB / 2-CPU ARM64 Hetzner server. Memory cap 2800 MiB; context 2048; prefill batch 32. No non-English result enters these rankings. These are measured model variants on a small controlled dataset, not a global leaderboard.','',
'## Updated English structured-task ranking','',
'All rows use the same seven English cases repeated twice. Order: correctness, valid JSON, native tool-call success, then median request time. Some earlier text timings used the runtime default batch. Conversation quality is a separate, incompletely measured capability.','',
'| Rank | Model | Correct checks | JSON syntax | Native tool call | Median seconds |','| --- | --- | --- | --- | --- | --- |']
for i,m in enumerate(ranked,1):lines.append(f"| {i} | {pretty(m['model'])} | {m['passed']}/14 | {m['json_valid']}/14 | {'pass' if m['native_tool_passed'] else 'fail'} | {fmt(m['median_seconds'])} |")
lines+=['','Always-thinking candidates with empty, length-limited final answers in a majority of the fourteen checks are listed as budget-incompatible rather than assigned an intrinsic accuracy rank: '+json.dumps(budget_limited), '','## Updated image analytics ranking','',
'Each model below completed the same five schema-constrained cases. Within ties, tested resolution and the mean of first-photo/first-poster time determine descriptive order. This is not evidence of broad statistical superiority. Raw-format checks remain visible; schemas can correct format errors but not false visual values.','',
'| Rank | Model | Correct schema answers | Raw checks | Image dimension | First photo seconds | First poster seconds |','| --- | --- | --- | --- | --- | --- | --- |']
for i,m in enumerate(vision,1):lines.append(f"| {i} | {pretty(m['model'])} | {m['schema_passed']}/{m['schema_total']} | {m['raw_passed']}/{m['raw_total']} | {m['max_image_dimension']} | {fmt(m['first_photo_seconds'])} | {fmt(m['first_poster_seconds'])} |")
lines+=['','## New candidate eligibility and outcomes','',
'| Model | Task | Outcome | Checks | OOM-kill delta | New package removed |','| --- | --- | --- | --- | --- | --- |']
for work in ['vision','text']:
 for m in main[work]+extra[work]:lines.append(f"| {pretty(m['model'])} | {work} | {m['status']} | {score(m['tests'])} | {m.get('oom_kill_delta','—')} | {m.get('new_package_removed','—')} |")
lines+=['','A load/import/timeout failure is not a bad accuracy score. A partial suite is excluded from the comparable ranking. For reasoning models, a length-limited empty final answer can reflect the fixed short-output profile. Check done_reason/output-token counts in raw results before generalizing.','',
'## English conversation samples (not an automated quality ranking)','']
for m in main['text']+extra['text']:
 if 'english_chat_sample' in m:lines+=['### '+pretty(m['model']),'','> '+m['english_chat_sample'].get('response','').replace('\n','\n> '),'']
lines+=['## New failures retained','']
for work in ['vision','text']:
 for m in main[work]+extra[work]:
  for attempt in m.get('image_attempts',[]):
   if not attempt['ok']:lines.append(f"- {pretty(m['model'])}, image {attempt['max_image_dimension']}: {attempt.get('error')}")
  if m.get('load') and not m['load']['ok']:lines.append(f"- {pretty(m['model'])}, load: {m['load'].get('error')}")
  if m.get('error'):lines.append(f"- {pretty(m['model'])}: {m['error']}")
  for group in ['tests','schema_tests']:
   for t in m.get(group,[]):
    if not t['passed']:lines.append(f"- {pretty(m['model'])}, {group}/{t['name']}, trial {t.get('trial','schema')}: {json.dumps(t.get('response',''),ensure_ascii=False)}"+(f"; {t.get('error')}" if not t['ok'] else ''))
lines+=['','## Interpretation and operations','',
'Only two controlled images and a handful of English tasks were used. Repeated deterministic prompts are not independent quality examples. Validate selected models on unseen project examples before accepting them for production. New-image latency is more useful than cached-image medians for a queue of different photos. Some schema timing measurements are warm and should not be compared directly across rounds; the table uses first-photo/poster queries instead.','',
'All inference is local to Hetzner. Cached listing/OSM facts were reused; no new database access or non-English test was performed. No production model or routing change was deployed. Newly downloaded weights were removed after metadata/results recording to preserve disk; selected candidates need to be pulled again for use. Existing model packages are preserved.','',
'Publisher source URLs and exact candidate tags are in plan.json / plan-extra.json. Raw results record resolved model digests, settings, outputs, errors, cleanup and before/after inventories. Licenses vary; this benchmark does not label all candidates Apache/open-source.','',
'Original restoration, main: '+json.dumps(main.get('restored_original')),
'Original restoration, extra: '+json.dumps(extra.get('restored_original'))]

reasoning=json.loads((ROOT/'reasoning-check.json').read_text()) if (ROOT/'reasoning-check.json').exists() else {'models':[]}
lines+=['','## Separate English reasoning-budget checks','','One case per selected model, explicit think=true, 1024 output tokens, same 2048 context and memory cap. These are not part of the short-output ranking. The LFM2.5-2.6B publisher documents it as always-thinking: https://huggingface.co/LiquidAI/LFM2.5-2.6B#chat-template','']
for m in reasoning['models']:
 lines.append('- '+pretty(m['model'])+': '+json.dumps(m,ensure_ascii=False))

if (ROOT/'CONCLUSIONS.md').exists():
 pos=lines.index('## Updated English structured-task ranking');lines[pos:pos]=(ROOT/'CONCLUSIONS.md').read_text().splitlines()+['']
(ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n');print(ROOT/'REPORT.md')
