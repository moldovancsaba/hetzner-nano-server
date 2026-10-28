"""Publish comparable completed-cohort metrics, keeping separate jobs and old evidence apart."""
import argparse,datetime,hashlib,json,random,statistics
from pathlib import Path
from scoring import recognition_summary,moderation_summary
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--recognition-only',action='store_true');recognition_only=parser.parse_args().recognition_only
r=json.loads((ROOT/'recognition-results.json').read_text());m={'models':[]} if recognition_only else json.loads((ROOT/'moderation-results.json').read_text())
rm=json.loads((ROOT/'recognition-manifest.json').read_text());mm=json.loads((ROOT/'moderation-manifest.json').read_text())
assert r['status']=='completed' and len(r['models'])==5,'Recognition must finish; no partial leaderboard'
if not recognition_only:assert m['status']=='completed' and len(m['models'])==5,'Moderation must finish before its leaderboard'
assert all(x['status']=='completed' and len(x['tests'])==32 and len(x['robustness'])==9 and len(x['counts'])==8 for x in r['models'])
assert all(x['status']=='completed' and len(x['tests'])==len(mm['cases']) and len(x['robustness'])==1 for x in m['models'])
protocol=json.loads((ROOT/'protocol.json').read_text())
for filename in ['recognition-manifest.json','moderation-manifest.json']:
    actual=hashlib.sha256((ROOT/filename).read_bytes()).hexdigest()
    assert actual==protocol['manifest_sha256'][filename], 'Reference manifest changed: '+filename
assert r['manifest_sha256']==protocol['manifest_sha256']['recognition-manifest.json']
assert hashlib.sha256((ROOT/'scoring.py').read_bytes()).hexdigest()==protocol['scorer_sha256'], 'Unversioned scorer change'
for entry in r['models']:
    for field,cases in [('tests',rm['recognition']),('robustness',rm['robustness']),('counts',[case for case in rm['recognition'] if case.get('count_probe')])]:
        assert {row['id'] for row in entry[field]}=={case['id'] for case in cases}, 'Missing/duplicate recognition cases'
if not recognition_only:
    assert m['manifest_sha256']==protocol['manifest_sha256']['moderation-manifest.json']
    for entry in m['models']:
        for field,cases in [('tests',mm['cases']),('robustness',mm['robustness'])]:
            assert {row['id'] for row in entry[field]}=={case['id'] for case in cases}, 'Missing/duplicate moderation cases'
        same=next(row for row in r['models'] if row['model']==entry['model'])
        assert entry['tag']['digest']==same['tag']['digest'], 'Artifact changed between task evaluations'
rec=[recognition_summary(x,rm) for x in r['models']];mod=[moderation_summary(x,mm) for x in m['models']]
rec.sort(key=lambda x:(-x['readiness_score'],-x['valid_rate'],x['median_seconds'],x['model']))
mod.sort(key=lambda x:(-x['macro_f2'],-x['macro_specificity'],-x['valid']/x['total'],x['median_seconds'],x['model']))
for row in rec+mod:
    row['tested_profile']={'max_image_edge':640,'num_ctx':2048,'num_batch':32,**({'think':False} if row['model']=='qwen3.5:0.8b' else {})}
for row in mod:row.update(benchmark_version='vision-evaluation.v1',ranking_metric='macro_f2')
(ROOT/'recognition-summary.json').write_text(json.dumps(rec,indent=2)+'\n')
if not recognition_only:(ROOT/'moderation-summary.json').write_text(json.dumps(mod,indent=2)+'\n')
old=json.loads((ROOT.parent/'round4/rankings.json').read_text())
rankings={'generated_utc':r['finished_utc'],'scope':'Broader service-contract image cohort; English historical ranking unchanged. No cross-dataset score mixing.','english_policy':old['english_policy'],'english':old['english'],'english_budget_limited':old['english_budget_limited'],'image_policy':'65% mean reference-supported object F1 + 35% OCR target recall, with invalid service responses scoring zero. Then valid response rate, then median inference wall time. Counts and paired robustness separate.','image':[],'image_service_ineligible':[]}
for row in rec:
    if row['valid']<1 or row['oom_kill_delta']:
        rankings['image_service_ineligible'].append({'model':row['model'],'reason':'No usable response under the current actual recognition contract, or resource failure','valid':row['valid'],'total':row['total_images'],'evidence':'benchmarks/vision-evaluation/recognition-results.json'});continue
    rankings['image'].append({k:row[k] for k in ['model','readiness_score','valid','total_images','valid_rate','object_reference_f1','object_recall','ocr_target_recall','ocr_correct','ocr_total','count_correct','count_total','median_seconds','p95_seconds','tested_profile']}|{'max_image_dimension':640,'benchmark_version':'vision-evaluation.v1','evidence':'benchmarks/vision-evaluation/recognition-results.json'})
assert rankings['image'],'No image model eligible for a ranked default'
(ROOT/'rankings.json').write_text(json.dumps(rankings,indent=2)+'\n')

def percent(value):return f'{100*value:.1f}%'
def paired_interval(best,other):
    a={x['id']:x for x in best['scored_cases']};b={x['id']:x for x in other['scored_cases']};obj=[x['id'] for x in rm['recognition'] if x['task']=='recognition'];ocr=[x['id'] for x in rm['recognition'] if x['task']=='ocr_vqa'];rng=random.Random(20261028);deltas=[]
    for _ in range(2000):
        os=rng.choices(obj,k=len(obj));ts=rng.choices(ocr,k=len(ocr));deltas.append(.65*statistics.mean(a[i]['score']-b[i]['score'] for i in os)+.35*statistics.mean(a[i]['score']-b[i]['score'] for i in ts))
    deltas.sort();return {'versus':other['model'],'point_delta':best['readiness_score']-other['readiness_score'],'paired_bootstrap_95':[deltas[49],deltas[1949]],'note':'Descriptive stratified paired resampling on this selected cohort; no multiple-comparison adjustment or production guarantee.'}
ci=[paired_interval(rec[0],other) for other in rec[1:]]
(ROOT/'recognition-comparison-intervals.json').write_text(json.dumps(ci,indent=2)+'\n')
lines=['# Broader image evaluation — 28 October 2026','','Completed comparison on the real 4 GB / two-CPU ARM64 Hetzner service. Earlier two-image scores were screening results and are not mixed into this leaderboard. English text and non-English rankings are unchanged.','','## Recognition: actual Camera service contract','','24 COCO photographs plus eight photographed-text cases, with reference labels reviewed before inference. The score is 65% reference-supported object F1 and 35% OCR target recall. Invalid/failed service responses score zero. This is a selected public research cohort, not representative Camera production accuracy.','','| Model | Readiness score | Usable API responses | Object F1 | OCR targets | Count probes | Median / p95 seconds |','| --- | --- | --- | --- | --- | --- | --- |']
for x in rec:lines.append(f"| {x['model']} | {percent(x['readiness_score'])} | {x['valid']}/32 | {percent(x['object_reference_f1'])} | {int(x['ocr_correct'])}/{x['ocr_total']} | {x['count_correct']}/{x['count_total']} | {x['median_seconds']:.2f} / {x['p95_seconds']:.2f} |")
lines+=['','Equivalent terms such as tabby cat/cat and sofa/couch are accepted. Compound nouns are disambiguated: hot dog is not dog, teddy bear is not wild bear. Source-supported coarse-object F1 does not certify every color, relationship or sentence in a free-form description. Counting is a native capability probe, not an exposed question/count API. Its six one-object and two two-object scenes give an always-one baseline of 6/8; the eight probes are too small/unbalanced for a broad counting claim.','', '### Paired uncertainty','']
for item in ci:lines.append('- Winner versus '+item['versus']+': point delta '+percent(item['point_delta'])+'; descriptive paired 95% interval '+str([round(v,4) for v in item['paired_bootstrap_95']])+'.')
lines+=['','### Robustness, separate from independent-image counts','','Nine paired dim/compression/instruction variants per model, derived from four base cases (the injection case reuses the dog photo). These are not additional independent scenes.','']
for x in rec:
    groups={}
    for row in x['robustness']:groups.setdefault(row['condition'],[]).append(row)
    lines.append('- '+x['model']+': '+', '.join(condition+' mean reference score '+percent(statistics.mean(z['score'] for z in rows))+' ('+str(sum(z['valid'] for z in rows))+'/'+str(len(rows))+' usable)' for condition,rows in groups.items()))
recognition_lines=lines+['','## Scope and evidence','','32 distinct primary photographs; paired robustness/count probes are not extra independent scenes. Public annotations plus one assistant visual review, not two-human adjudication. Public validation data may have appeared in pretraining. No representative Camera production cohort, complete caption-truth, movie, multi-image or non-English certification.','','Qwen uses explicit think=false for bounded image output. Nine failed as-is-profile cases remain separate diagnostics; the full corrected-profile cohort is used here. Other models were unchanged.','','[Raw completed run](recognition-results.json), [references](recognition-manifest.json), [per-case scores](recognition-summary.json), [protocol and revisions](protocol.json). Moderation is a separate evaluation and does not change this ranking.']
(ROOT/'REPORT-RECOGNITION.md').write_text('\n'.join(recognition_lines)+'\n')
image_lines=['# General image recognition ranking','','Current comparable ranking uses the [broader actual-service evaluation](../vision-evaluation/REPORT-RECOGNITION.md), not the old two-image screening. English, moderation and non-English remain separate.','','| Rank | Model | Readiness score | Usable responses | Object reference F1 | OCR targets | Median seconds |','| --- | --- | --- | --- | --- | --- | --- |']
for i,x in enumerate(rankings['image'],1):image_lines.append(f"| {i} | {x['model']} | {percent(x['readiness_score'])} | {x['valid']}/32 | {percent(x['object_reference_f1'])} | {int(x['ocr_correct'])}/8 | {x['median_seconds']:.2f} |")
image_lines+=['','The score is cohort-specific, not a general accuracy percentage. Older variants retain their historical [screening evidence](../round4/rankings.json) and may remain explicit alternatives, but their old scores are not numerically mixed into this ranking.']
(ROOT.parent/'rankings/IMAGES.md').write_text('\n'.join(image_lines)+'\n')
if recognition_only:
    print(json.dumps({'recognition_winner':rankings['image'][0]['model'],'recognition_models':len(rec),'moderation':'separate, not yet published'}));raise SystemExit(0)
lines+=['','## Moderation: independent nine-category comparison','','41 distinct images: 34 photographic/photo-like images, two source illustrations and five controlled English text/shape probes. A further paired instruction-in-image challenge is separate. Primary order: equal-category macro F2, specificity, valid-response rate, then latency. Positive-reference abstentions/invalid outputs count as missed detections. Unknown references are not negative labels. No flags never means approval.','','| Model | Macro F2 | Macro detection recall | Macro specificity | Valid outputs | Median seconds |','| --- | --- | --- | --- | --- | --- |']
for x in mod:lines.append(f"| {x['model']} | {percent(x['macro_f2'])} | {percent(x['macro_detection_recall'])} | {percent(x['macro_specificity'])} | {x['valid']}/{x['total']} | {x['median_seconds']:.2f} |")
# Transparent trivial baselines expose class imbalance without extra inference.
baselines=[]
for label,value in [('always_negative',False),('always_positive',True),('always_uncertain',None)]:
    synthetic={'model':label,'status':'completed','tests':[{'id':case['id'],'valid':True,'seconds':0,'parsed':{'categories':dict.fromkeys(mm['categories'],value)}} for case in mm['cases']]}
    summary=moderation_summary(synthetic,mm)
    baselines.append({key:summary[key] for key in ['model','macro_f2','macro_detection_recall','macro_specificity']})
(ROOT/'moderation-baselines.json').write_text(json.dumps(baselines,indent=2)+'\n')
lines+=['','Trivial reference baselines (no inference): '+ '; '.join(row['model']+' macro F2 '+percent(row['macro_f2']) for row in baselines)+'. The mostly negative dataset makes raw Boolean accuracy misleading; it is not the selection metric.']
lines+=['','The first two moderation scores are close and this small cohort does not establish general superiority. On these references, both Qwen and MiniCPM detected 0/2 controlled English hate-word positives and 1/3 violence positives. Qwen had fewer sexual-content false alarms (0 versus MiniCPM’s 10 known-negative cases), while MiniCPM detected one more drug-positive case (3/4 versus 2/4). These are observed tradeoffs, not calibrated operating guarantees.']
lines+=['','### Per-category findings','','Recall intervals are Wilson 95% intervals. Small positive counts produce wide uncertainty even if every positive is detected. Invalid/abstained positive references are included in the recall denominator.','']
for x in mod:
    lines+=['#### '+x['model'],'','| Category | Positives | Detected | Missed false | Positive abstentions / invalid | False positives | Recall 95% interval |','| --- | --- | --- | --- | --- | --- | --- |']
    for category,c in x['categories'].items():lines.append(f"| {category} | {c['positive']} | {c['tp']} | {c['fn']} | {c['review_positive']} / {c['invalid_positive']} | {c['fp']} | {str([round(v,3) for v in c['recall_wilson_95']])} |")
lines+=['','### Paired instruction-in-image challenge','','A museum/archive flag photograph was also tested with a visible instruction overlay. This is one paired case per model, not an independent image cohort or comprehensive prompt-injection certification. Category changes can also reflect visual interference.','', '| Model | Base valid | Base hateSymbols | Overlay valid | Overlay hateSymbols |', '| --- | --- | --- | --- | --- |']
robust=[]
for entry in m['models']:
    for case in mm['robustness']:
        base=next(row for row in entry['tests'] if row['id']==case['base_case'])
        variant=next(row for row in entry['robustness'] if row['id']==case['id'])
        def hate(row):
            parsed=row.get('parsed');categories=parsed.get('categories',{}) if isinstance(parsed,dict) else {}
            return categories.get('hateSymbols') if isinstance(categories,dict) and row.get('valid') else 'invalid'
        item={'model':entry['model'],'base_id':base['id'],'variant_id':variant['id'],'base_valid':base['valid'],'variant_valid':variant['valid'],'base_hateSymbols':hate(base),'variant_hateSymbols':hate(variant)}
        robust.append(item)
        lines.append('| '+entry['model']+' | '+str(base['valid'])+' | '+str(hate(base))+' | '+str(variant['valid'])+' | '+str(hate(variant))+' |')
(ROOT/'moderation-robustness.json').write_text(json.dumps(robust,indent=2)+'\n')
lines+=['','### Photographs versus controlled text probes','','Hate-word positives are controlled English text probes; no photographic/multilingual hate-word recall is established. The photograph-only macro score excludes categories without photographic positives and is therefore not interchangeable with the nine-category primary score.','']
photo_manifest={**mm,'cases':[c for c in mm['cases'] if c['medium']=='photograph']};photo_ids={c['id'] for c in photo_manifest['cases']}
photo=[]
for entry in m['models']:
    subset={**entry,'tests':[t for t in entry['tests'] if t['id'] in photo_ids]};row=moderation_summary(subset,photo_manifest);photo.append(row);lines.append('- '+row['model']+': photograph-only macro F2 '+percent(row['macro_f2'])+' over '+str(sum(c['positive']>0 for c in row['categories'].values()))+' categories with photographic positives.')
(ROOT/'moderation-photo-summary.json').write_text(json.dumps(photo,indent=2)+'\n')
lines+=['','## Resource evidence','','All candidates used the same 2800 MiB / two-CPU container cap, no GPU and no swap. The figures below are sampled cgroup memory (including cache), not exact model-only RAM or a guarantee that no shorter spike occurred. See [runtime audit](runtime-audit-before-profile-fix.json).','','| Model | Recognition sampled peak MiB | Moderation sampled peak MiB | Recognition / moderation OOM kills |','| --- | --- | --- | --- |']
for entry in r['models']:
    other=next(row for row in m['models'] if row['model']==entry['model'])
    recognition_peak=max((row.get('peak_cgroup_bytes',0) for field in ['tests','robustness','counts'] for row in entry[field]),default=0)
    moderation_peak=max((row.get('peak_cgroup_bytes',0) for field in ['tests','robustness'] for row in other[field]),default=0)
    lines.append('| '+entry['model']+' | '+str(round(recognition_peak/1048576,1))+' | '+str(round(moderation_peak/1048576,1))+' | '+str(entry.get('oom_kill_delta',0))+' / '+str(other.get('oom_kill_delta',0))+' |')
lines+=['','## What this establishes and what it does not','','Across the primary cohorts there are 70 distinct source images (63 photographic/photo-like images, two source illustrations and five controlled probes); three benign COCO photos are shared between tasks. Ten paired variants, repeated model calls, and eight reused count probes are not inflated into independent image counts.','','Public annotations/answer consensus plus one assistant visual review form the reference. No two-human adjudication or representative Camera/customer cohort was available. The owner chose public research data only. Labels were frozen before inference; the scorer received a documented, equally applied compound-noun bug fix before final scoring. No model-as-judge or model-specific answer adjustment was used. Public validation images may have appeared in model pretraining.','','Moderation coverage gaps remain explicit: two clear adult-appearing sexual-act images, no independently certified identity/age provenance, English controlled hate words, and limited injury/depicted-harm coverage. Ambiguous/young-appearing sexual candidates were excluded and their local derivatives removed. These results do not certify autonomous moderation, broad gore/assault detection, movies, multi-image reasoning, training, or any non-English capability. Human review remains mandatory.','','Recognition calls used the actual authenticated Camera API and one outstanding FIFO test job, so production could interleave. Waiting and inference time are separate. Moderation used the identical live prompt/schema under a renewable idle lease per image and yielded between cases. Resource limits/runtime were unchanged. Cgroup peaks include cache and can miss sub-sample spikes; no GPU/host-cold/load-test claim is made.','','[Protocol](protocol.json), [recognition labels](recognition-manifest.json), [moderation labels](moderation-manifest.json), [recognition detail](recognition-summary.json), [moderation detail](moderation-summary.json), [raw recognition run](recognition-results.json), and [raw moderation run](moderation-results.json). Source images stay private and are not training-approved.']
if (ROOT/'service-diagnostics.json').exists():lines+=['','## Service failure diagnostic','','A separate non-scoring replay confirmed a baseline response exhausted the 256-token output limit, ending with incomplete JSON and repeated non-text object names in visible_text. Raising a token limit alone would not establish truthful OCR. See [the exact diagnostic](service-diagnostics.json). This proves that failure cause for the replayed case, not every failed response.']
if all((ROOT/name).exists() for name in ['final-deployment.json','public-verification.json','final-runtime-audit.json']):
    deployed=json.loads((ROOT/'final-deployment.json').read_text());verified=json.loads((ROOT/'public-verification.json').read_text());audit=json.loads((ROOT/'final-runtime-audit.json').read_text())
    assert deployed['deployed'] and verified['passed'] and audit['passed']
    assert deployed['policy_id']==verified['policy_id']==audit['policy_id']
    assert deployed['defaults']['image_recognition']==rankings['image'][0]['model'] and deployed['defaults']['image_moderation']==mod[0]['model']
    lines+=['','## Deployment, verification and cleanup','','Recorded policy: `'+deployed['policy_id']+'`. Recognition defaults to `'+deployed['defaults']['image_recognition']+'`; moderation defaults to `'+deployed['defaults']['image_moderation']+'`; text stays `'+deployed['defaults']['text_chat']+'`. Explicit tested alternatives remain available.','','All '+str(len(verified['checks']))+' bounded public routing checks passed, including authorization, ranked auto jobs, explicit moderation selection, human-review semantics, mixed-work serialization, result deletion and text restoration. This verifies operation, not accuracy.','','Temporary server input folders were removed. HTTPS, gateway, Pandora and both discovery/cleanup timers are active; default digests match; no OOM kills were recorded. Free disk was '+str(audit['disk_free_gib'])+' GiB, below the soft 8 GiB planning target but above the 4 GiB floor. Protected top-five/recent-use weights were retained under the existing policy.','','[Deployment evidence](final-deployment.json), [public verification](public-verification.json), [health and cleanup audit](final-runtime-audit.json).']
(ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'recognition_winner':rankings['image'][0]['model'],'moderation_winner':mod[0]['model'],'recognition_models':len(rec),'moderation_models':len(mod)}))
