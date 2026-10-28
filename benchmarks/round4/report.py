"""Merge completed, comparable new candidates into independent historical rankings."""
import datetime,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
data=json.loads((ROOT/'results.json').read_text())
assert data.get('finished_utc') and data.get('restore',{}).get('ok'),'Run not finished/restored'
assert len(data['models'])==10,'Need ten attempted new candidates'
previous=json.loads((ROOT.parent/'round3/rankings.json').read_text())
rankings={**previous,'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Round 4 new candidates plus historical eligible variants; 4 GB ARM64 CPU server. English and images independent.'}
rows=data['models']
for m in rows:
    if m['status']!='completed' or m.get('oom_kill_delta',0):continue
    tests=m['tests']
    if m['task']=='text' and len(tests)==14:
        limited=sum(t.get('done_reason')=='length' and not t.get('response','').strip() for t in tests)
        if limited>7:
            rankings['english_budget_limited'].append({'model':m['model'],'empty_length_limited_cases':limited,'total':14});continue
        rankings['english'].append({'model':m['model'],'passed':sum(t['passed'] for t in tests),'total':14,'json_valid':sum(t['json_valid'] for t in tests),'native_tool_passed':m.get('tool_call',{}).get('passed',False),'median_seconds':round(statistics.median(t['seconds'] for t in tests),3),'evidence':'benchmarks/round4/results.json'})
    if m['task']=='vision' and len(m.get('schema_tests',[]))==5:
        rankings['image'].append({'model':m['model'],'schema_passed':sum(t['passed'] and t['keys_match'] for t in m['schema_tests']),'schema_total':5,'max_image_dimension':m['max_image_dimension'],'raw_passed':sum(t['passed'] for t in tests),'raw_total':len(tests),'first_photo_seconds':next(t['seconds'] for t in m['image_attempts'] if t['ok']),'first_poster_seconds':next(t['seconds'] for t in tests if t['name']=='poster_ocr' and t['trial']==1),'evidence':'benchmarks/round4/results.json'})
rankings['english'].sort(key=lambda x:(-x['passed'],-x['json_valid'],-x['native_tool_passed'],x['median_seconds']))
rankings['image'].sort(key=lambda x:(-x['schema_passed'],-x['max_image_dimension'],statistics.mean([x[k] for k in ['first_photo_seconds','first_poster_seconds'] if x[k] is not None])))
(ROOT/'rankings.json').write_text(json.dumps(rankings,indent=2)+'\n')
lines=['# Ten new candidates: 28 October 2026','','Five English text and five general still-image candidates, new to our test history. Some releases are older; this is not a claim of ten new releases. Moderation and non-English are unchanged.','','## Candidate outcomes','','| Candidate | Task | Outcome | Correct raw checks | JSON valid | Schema checks | Peak cgroup MiB | OOM kills |','| --- | --- | --- | --- | --- | --- | --- | --- |']
for m in rows:
    tests=m.get('tests',[]);schema=m.get('schema_tests',[])
    samples=tests+schema+m.get('image_attempts',[])+([m['load']] if m.get('load') else [])
    peak=max((x.get('peak_cgroup_bytes',0) for x in samples),default=0)/1024**2
    lines.append(f"| {m['model']} | {m['task']} | {m['status']} | {sum(t['passed'] for t in tests)}/{len(tests)} | {sum(t.get('json_valid',False) for t in tests)}/{sum('json_valid' in t for t in tests)} | {sum(t['passed'] for t in schema)}/{len(schema)} | {peak:.0f} | {m.get('oom_kill_delta',0)} |")
lines+=['','## Current-winner controls','','These reruns check regression and environment drift. Historical leaderboard timings are retained for existing variants; fresh control results remain separate rather than replacing their rankings based on one timing rerun.']
for m in data['controls']:lines.append(f"- {m['model']}: {m['status']}; {sum(t.get('passed',False) for t in m.get('tests',[]))}/{len(m.get('tests',[]))} raw checks; {sum(t['passed'] for t in m.get('schema_tests',[]))}/{len(m.get('schema_tests',[]))} schema checks.")
lines+=['','## Eligibility failures and limitations','']
for m in rows:
    if m.get('error'):lines.append('- '+m['model']+': '+m['error'].replace('\n',' ')[:1800])
    for t in m.get('image_attempts',[])+([m['load']] if m.get('load') else []):
        if not t['ok']:lines.append('- '+m['model']+': '+t.get('error','unknown').replace('\n',' ')[:1800])
lines+=['','Native tests used one renewable maintenance lease, draining the shared queue and temporarily refusing new inference. Cleanup was paused, candidate weights were tested serially and temporary packages removed after recording results/digests. The existing 2800 MiB memory cap, two CPUs, no swap and 2048-token benchmark profile were unchanged. Default service 8K profiles were restored afterward. Native tests do not update production usage.','','Seven cached English listing/OSM/prompt-injection cases repeated twice and two controlled images are a screening benchmark, not independent project holdouts or broad accuracy certification. Image schema constraints check format separately from expected visual values. Round-4 raw JSON validators additionally require exact keys for animal/count, remote count, OCR and missing address; older raw checks sometimes allowed extra keys. Therefore raw counts across rounds are descriptive, not a like-for-like leaderboard. The five constrained-schema checks retain the same expected answers and required keys. Tools test argument selection, not autonomous MongoDB/OSM access. No private database credentials, live images or user conversations were used. No video, moderation or non-English claim follows from these results.','','Cgroup memory includes page cache; 100 ms sampled peaks may miss shorter spikes. OOM counters are recorded separately. First-image requests include model/encoder startup; repeated-image latency is cache-warm. Empty length-limited reasoning answers are marked budget-incompatible, not intrinsically inaccurate. Pull/import/load failures receive no quality rank.','','Publisher URLs, revisions and license metadata are in plan.json and source-metadata.json. LiquidAI artifacts use their custom LFM license; listing a model is not blanket commercial/license approval. No remote model code was executed. Runtime was not upgraded to make a candidate pass.','','Raw evidence: [results.json](results.json). Rankings: [rankings.json](rankings.json).']
(ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
for field,name,title in [('english','ENGLISH','English structured text'),('image','IMAGES','General still-image recognition')]:
    table=['# '+title+' ranking','','Updated with [round 4](../round4/REPORT.md). Small controlled screening, not a global leaderboard. Moderation and non-English remain independent.','']
    if field=='english':
        table+=['| Rank | Model | Correct | JSON valid | Native tool | Median seconds |','| --- | --- | --- | --- | --- | --- |']
        for i,m in enumerate(rankings[field],1):table.append(f"| {i} | {m['model']} | {m['passed']}/14 | {m['json_valid']}/14 | {m['native_tool_passed']} | {m['median_seconds']:.3f} |")
    else:
        table+=['| Rank | Model | Correct schema | Raw checks | Image edge | First photo seconds | First poster seconds |','| --- | --- | --- | --- | --- | --- | --- |']
        for i,m in enumerate(rankings[field],1):table.append(f"| {i} | {m['model']} | {m['schema_passed']}/5 | {m['raw_passed']}/{m['raw_total']} | {m['max_image_dimension']} | {m['first_photo_seconds']} | {m['first_poster_seconds']} |")
    table+=['','Correctness determines ranking first. Timing tie-breaks are descriptive and sensitive to cache/runtime conditions; they do not establish statistical quality superiority. Current defaults must match the generated task policy and verified context requirements.']
    (ROOT.parent/'rankings'/f'{name}.md').write_text('\n'.join(table)+'\n')
print(json.dumps({'text_winner':rankings['english'][0]['model'],'image_winner':rankings['image'][0]['model'],'attempted':len(rows)}))
