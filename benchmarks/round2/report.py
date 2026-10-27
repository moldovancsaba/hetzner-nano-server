import json,pathlib,statistics
ROOT=pathlib.Path(__file__).parent
d=json.loads((ROOT/'results.json').read_text());retries=json.loads((ROOT/'vision-retries.json').read_text()) if (ROOT/'vision-retries.json').exists() else {'models':[]};schema=json.loads((ROOT/'schema-vision.json').read_text()) if (ROOT/'schema-vision.json').exists() else {'models':[]}
supplement=json.loads((ROOT/'supplement-text.json').read_text()) if (ROOT/'supplement-text.json').exists() else {'text':[]}
from english_results import build
texts=build(ROOT)
def label(s):return s.replace('hf.co/ggml-org/','').replace('hf.co/QuantFactory/','').replace('-Instruct-GGUF:Q4_K_M',' Q4').replace('-Instruct-GGUF:Q8_0',' Q8')
def score(ts):return f"{sum(bool(t.get('passed')) for t in ts)}/{len(ts)}" if ts else 'not run'
def median(ts):
 xs=[t['seconds'] for t in ts if t.get('ok')];return f'{statistics.median(xs):.2f}' if xs else '—'
def shorterr(m):return m.get('first_image',{}).get('error',m.get('error','')).replace('\n',' ')[:240]
lines=['# Separate image analytics and chat/text benchmark','',
'All runs used the existing 4 GB, 2-CPU ARM64 server, with the 2800-MiB container memory limit unchanged. Image models and English text models are evaluated independently. Non-English capabilities have a separate report and acceptance process. No single-model-for-both requirement applies.','',
'## Image analytics: initial run','',
'| Model | Outcome | Checks passed | JSON syntax | First request seconds (success/failure) |',
'| --- | --- | --- | --- | --- |']
for m in d['vision']:
 ts=m['tests'];js=[t for t in ts if t.get('json_valid') is not None]
 lines.append(f"| {label(m['model'])} | {m.get('status')} | {score(ts)} | {sum(t.get('json_valid') is True for t in js)}/{len(js)} | {m.get('first_image',{}).get('seconds','—')} |")
lines+=['','Gemma4:e2b was also attempted before this suite and failed with a Gemma4Assistant ctx_other context-initialization error. gemma4-preflight.json preserves the response. The alternate E2B-it-QAT package was tested with an actual photo and failed with a killed runner. Its exact metadata is in gemma4-qat-metadata.json. Failed Gemma packages were removed after recording evidence to recover disk space. These failures establish inability to complete these requests in this environment/configuration, not poor model quality.','',
'## Image-specific retries','',
'Granite Vision originally needed 3706 input tokens, so its retry uses 4096 context. Qwen3-VL and Ministral retry 320-pixel inputs. All retries set num_batch=32 to reduce prefill working memory. The memory cap remains 2800 MiB. These are dedicated image-processing settings, independent of chat.','',
'| Model | Context | Max image dimension | Prefill batch | Outcome | Checks passed | First request seconds (success/failure) | OOM-kill delta |',
'| --- | --- | --- | --- | --- | --- | --- | --- |']
for m in retries['models']:
 lines.append(f"| {label(m['model'])} | {m['context']} | {m['max_image_dimension']} | {m.get('prefill_batch',32)} | {m.get('status')} | {score(m['tests'])} | {m.get('first_image',{}).get('seconds','—')} | {m.get('oom_kill_delta','—')} |")
lines+=['','## JSON schema constraints for image output','',
'One trial per structured case, using required field names/types and no additional properties. Expected answer values (cat, 2, room 12, 09:00, etc.) are NOT supplied by the schema. This tests whether constrained decoding makes outputs usable. Field/type validity still does not establish truthful values.','',
'| Model | Image dimension | Context | Correct values | Valid JSON | Median seconds |',
'| --- | --- | --- | --- | --- | --- |']
for m in schema['models']:
 ts=m['tests'];lines.append(f"| {label(m['model'])} | {m['max_image_dimension']} | {m['context']} | {score(ts)} | {sum(t.get('json_valid') is True for t in ts)}/{len(ts)} | {median(ts)} |")
lines+=['','## English chat and structured text','',
'| Model | Original listing/OSM checks (14) | English chat checks (4) | English JSON syntax (18) | Native tool call | Median structured response seconds |',
'| --- | --- | --- | --- | --- | --- |']
chatnames={'chat_followup','hungarian_extraction','chat_unknown_secret'}
for m in texts:
 ts=[t for t in m['tests'] if t['name']!='hungarian_extraction'];a=[t for t in ts if t['name'] not in chatnames];b=[t for t in ts if t['name'] in chatnames];tool=m.get('tool_call',{})
 lines.append(f"| {label(m['model'])} | {score(a)} | {score(b)} | {sum(t.get('json_valid') is True for t in ts)}/{len(ts)} | {('pass' if tool.get('passed') else 'fail') if tool else 'not run'} | {median(ts)} |")
lines+=['','English chat checks cover follow-up recall and refusal to invent an unknown password. Hungarian extraction and advice are excluded from all English scores, medians and recommendations; see ../non-english/REPORT.md. Historical raw files preserve the original mixed observations.','',
'## Free-form chat samples for human review','']
for m in texts:
 lines.append('### '+label(m['model']))
 for c in m.get('chat_samples',[]):
  if c.get('language')!='en':continue
  lines.append(f"\n**{c['language']}**, {c['seconds']:.2f}s, finish={c.get('done_reason')}:\n")
  lines.append('> '+c.get('response','').replace('\n','\n> '))
lines+=['','## Raw failed cases and load diagnostics','']
for section in [d['vision'],retries['models'],schema['models'],texts]:
 for m in section:
  if shorterr(m):lines.append(f"- {label(m['model'])}: {shorterr(m)}")
  for t in m.get('tests',[]):
   if t['name']!='hungarian_extraction' and not t.get('passed'):lines.append(f"- {label(m['model'])}, {t['name']}, trial {t.get('trial','schema')}: {json.dumps(t.get('response',''),ensure_ascii=False)}"+(f"; error {t.get('error')}" if not t.get('ok') else ''))
lines+=['','## Scope and restoration','',
'Two images are not a general image benchmark. Each main case is repeated twice with fixed settings; repetitions are not independent examples. Exact image dimensions/context and output limits can affect eligibility and quality. First-image time includes model loading/encoding; repeated inputs may benefit from caching. Short warm request medians are not an SLA.','',
'Runtime OOM events can kill an inference child while the Ollama container itself stays running. Do not infer no OOM just from Docker OOMKilled=false. Retry oom_kill deltas are read from the container cgroup. Initial failure diagnostics also recorded cgroup events.','',
'Atlas and OSM inputs are cached public results from the earlier bounded real-data benchmark. This extension does not add production tools or image uploads to Pandora. Source URLs, fixture descriptions and reproduction steps are in README.md.','',
'Original model restoration recorded for main suite: '+json.dumps(d.get('restored_original')),
'Original model restoration recorded for retries: '+json.dumps(retries.get('restored_original')),
'Original model restoration recorded for schema phase: '+json.dumps(schema.get('restored_original'))]
if (ROOT/'DECISIONS.md').exists():
 pos=lines.index('## Image analytics: initial run');lines[pos:pos]=(ROOT/'DECISIONS.md').read_text().splitlines()+['']
(ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n');print(ROOT/'REPORT.md')
