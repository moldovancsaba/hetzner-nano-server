"""Builds REPORT.md and summary.json for the forbidden-content benchmark from manifest.json (reference labels) and results.json.
Per model and category it counts true/false positives and negatives, review (null) answers and invalid responses, and lists disagreements.
The decision and limitation text is fixed in this script. Prints a per-model summary."""
from pathlib import Path
import json,statistics
R=Path(__file__).parent
manifest=json.loads((R/'manifest.json').read_text());data=json.loads((R/'results.json').read_text());cases={x['id']:x for x in manifest['cases']};lines=['# Forbidden-content benchmark results','','25 reviewed images; two small models; each category scored independently. **No production approval follows from this small screening test.**','','See [method, sources and limitations](README.md), [reference labels](manifest.json), and [raw measurements](results.json).','']
lines += ['## Decision', '', 'Neither tested profile is suitable as a standalone forbidden-content filter. The 450M model returned decisive but incorrect negatives in several categories. The 1.6B model overwhelmingly abstained, including where its evidence sentence correctly described beer. This is a failure of this combined prompt/schema/runtime profile, not proof of intrinsic inability or a calibrated uncertainty estimate. A simpler per-category prompt and explicit present/absent/uncertain string schema should be tested on a separate holdout before changing production behavior.', '', 'All categories were exercised, but sexual-content references cover pornographic poses rather than explicit acts; violence has one restraint example; gesture and hate-symbol positives are illustrated. These gaps prevent comprehensive category certification.', '']
summary=[]
for model in data['models']:
 rows=model['tests'];valid=[r for r in rows if r.get('ok') and r.get('schema_valid')];ms={'model':model['model'],'status':model['status'],'valid':len(valid),'total':len(rows),'categories':{}}
 lines += ['## '+model['model'],'',f"Status: {model['status']}. Schema-valid successful responses: {len(valid)}/{len(rows)}. OOM-kill delta: {model.get('oom_kill_delta')}. Newly downloaded package removed: {model.get('new_package_removed')}.",'']
 if valid:lines += [f"Median case response: {statistics.median(r['seconds'] for r in valid):.2f} seconds; first image: {rows[0]['seconds']:.2f} seconds, including reported model load {rows[0]['load_seconds']:.2f} seconds. Largest post-request sampled container memory: {max(r['memory']['current'] for r in rows)/1024**3:.2f} GiB. This sample is not peak memory.",'']
 lines += ['| Category | Positive refs | Negative refs | Unknown refs | TP | FN | FP | TN | Review on positive/negative | Correct review on unknown |','| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
 for c in manifest['categories']:
  counts={k:0 for k in ['positive','negative','unknown','tp','fn','fp','tn','review_positive','review_negative','review_unknown','invalid']}
  for ref in manifest['cases']:
   truth=ref['expected'][c];counts['unknown' if truth is None else 'positive' if truth else 'negative']+=1
   found=next((r for r in rows if r['id']==ref['id']),None)
   if found is None or not found.get('ok') or not found.get('schema_valid'):counts['invalid']+=1;continue
   pred=found['predictions'][c]
   if truth is None:
    if pred is None:counts['review_unknown']+=1
   elif pred is None:counts['review_positive' if truth else 'review_negative']+=1
   else:counts['tp' if truth and pred else 'fn' if truth else 'fp' if pred else 'tn']+=1
  ms['categories'][c]=counts
  lines.append('| '+' | '.join(str(v) for v in [c,counts['positive'],counts['negative'],counts['unknown'],counts['tp'],counts['fn'],counts['fp'],counts['tn'],str(counts['review_positive'])+'/'+str(counts['review_negative']),str(counts['review_unknown'])+'/'+str(counts['unknown'])])+' |')
 lines += ['','TP/FN/FP/TN use only explicit Boolean predictions on known references. Review/null is neither correct detection nor a decisive false negative. Invalid/missing responses are excluded from this confusion table and remain technical failures. Unknown references never establish a correct positive/negative decision.','', '### Disagreements and review cases','']
 for row in rows:
  if not row.get('ok') or not row.get('schema_valid'):lines.append('- '+row['id']+': invalid/failed response.');continue
  ref=cases[row['id']];diff=[c+': expected '+str(ref['expected'][c])+', got '+str(row['predictions'][c]) for c in manifest['categories'] if row['predictions'][c] is not ref['expected'][c]]
  if diff:lines.append('- '+row['id']+': '+'; '.join(diff)+'.')
 lines += [''];summary.append(ms)
lines += ['## Operational outcome','',f"Original chat model restored successfully: {data.get('restore',{}).get('ok')}. Loaded model(s): {', '.join(m['name'] for m in data.get('final_loaded',{}).get('models',[]))}.",'','No filter was deployed and no Fanmass settings changed. No movie, dense crowd, small-logo or non-English claim is supported by this benchmark. Category-specific real Fanmass holdouts and independent label adjudication are required before automated moderation.']
(R/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(R/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps([{k:v for k,v in s.items() if k!='categories'} for s in summary],indent=2))
