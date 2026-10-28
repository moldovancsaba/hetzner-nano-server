#!/usr/bin/env python3
"""Build deterministic task defaults from current separate ranking evidence."""
import argparse,hashlib,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build(root=ROOT):
 sources=json.loads((root/'config/ranking-sources.json').read_text());digests={};evidence=[]
 def walk(value):
  if isinstance(value,dict):
   name=value.get('name') or value.get('model')
   if isinstance(name,str) and isinstance(value.get('digest'),str):digests[name.lower()]=value['digest']
   for v in value.values():walk(v)
  elif isinstance(value,list):
   for v in value:walk(v)
 runtime_paths=[]
 if sources.get('runtime_profiles'):
  runtime_paths=[sources['runtime_profiles']]+json.loads((root/sources['runtime_profiles']).read_text()).get('evidence_files',[])
 legacy_paths=[sources[key] for key in ['legacy_screening','legacy_moderation','legacy_moderation_raw'] if sources.get(key)]
 paths=list(dict.fromkeys([sources['english_and_images'],sources['moderation'],sources['moderation_raw']]+sources['digest_evidence']+legacy_paths+runtime_paths))
 for name in paths:
  data=(root/name).read_bytes();evidence.append({'path':name,'sha256':hashlib.sha256(data).hexdigest()});walk(json.loads(data))
 ranked=json.loads((root/sources['english_and_images']).read_text());models={};defaults={}
 def add(task,model,rank,metrics,source,edge=640):
  digest=digests.get(model.lower())
  if not digest:raise ValueError('No tested artifact digest for '+model)
  entry=models.setdefault(model,{'id':model,'tested_digest':digest,'tasks':{}})
  profile={'max_image_edge':edge,'num_ctx':2048,'num_batch':32}
  measured=metrics.get('tested_profile',{})
  if set(measured)-{'max_image_edge','num_ctx','num_batch','think'}:raise ValueError('Unsupported tested profile field')
  if 'think' in measured and type(measured['think']) is not bool:raise ValueError('Invalid thinking control')
  profile.update(measured)
  entry['tasks'][task]={'rank':rank,'metrics':metrics,'evidence':source,'profile':profile}
 for task,field in [('text_chat','english'),('image_recognition','image')]:
  rows=ranked[field]
  if not rows:raise ValueError('No ranking for '+task)
  for rank,row in enumerate(rows,1):
   add(task,row['model'],rank,row,sources['english_and_images'],row.get('max_image_dimension',640))
   if row.get('benchmark_version')=='vision-evaluation.v1':models[row['model']]['tasks'][task].update(ranking_tier='broader_service_evaluation',current_rank=rank)
  defaults[task]=rows[0]['model']
 if sources.get('legacy_screening'):
  failed={row['model'] for row in ranked.get('image_service_ineligible',[])}
  for index,row in enumerate(json.loads((root/sources['legacy_screening']).read_text())['image'],1):
   model=row['model']
   if model in failed or 'image_recognition' in models.get(model,{}).get('tasks',{}):continue
   add('image_recognition',model,1000+index,row,sources['legacy_screening'],row.get('max_image_dimension',640))
   models[model]['tasks']['image_recognition'].update(ranking_tier='legacy_screening_not_comparable',current_rank=None)
 raw=json.loads((root/sources['moderation_raw']).read_text());moderation=[]
 moderation_rows=json.loads((root/sources['moderation']).read_text());use_macro=any(row.get('ranking_metric')=='macro_f2' for row in moderation_rows)
 if use_macro and not all(row.get('ranking_metric')=='macro_f2' for row in moderation_rows):raise ValueError('Mixed moderation benchmark methods')
 for row in moderation_rows:
  if row['status']!='completed' or row['total']<1:continue
  if use_macro:
   if not row.get('ranking_eligible') or row['valid']<1:continue
  elif row['valid']!=row['total']:continue
  cats=row['categories'];tests=next(m['tests'] for m in raw['models'] if m['model']==row['model'])
  metrics={'true_positives':sum(c['tp'] for c in cats.values()),'known_correct':sum(c['tp']+c['tn'] for c in cats.values()),'false_positives':sum(c['fp'] for c in cats.values()),'median_seconds':statistics.median(t['seconds'] for t in tests),'categories':cats}
  if use_macro:metrics.update({key:row[key] for key in ['macro_f2','macro_specificity','macro_detection_recall','valid','total','benchmark_version','tested_profile']})
  moderation.append((row['model'],metrics))
 if use_macro:moderation.sort(key=lambda pair:(-pair[1]['macro_f2'],-pair[1]['macro_specificity'],-pair[1]['valid']/pair[1]['total'],pair[1]['median_seconds'],pair[0]))
 else:moderation.sort(key=lambda pair:(-pair[1]['true_positives'],-pair[1]['known_correct'],pair[1]['false_positives'],pair[1]['median_seconds'],pair[0]))
 if not moderation:raise ValueError('No complete moderation evidence')
 for rank,(model,metrics) in enumerate(moderation,1):
  add('image_moderation',model,rank,metrics,sources['moderation'])
  if use_macro:models[model]['tasks']['image_moderation'].update(ranking_tier='broader_moderation_evaluation',current_rank=rank)
 defaults['image_moderation']=moderation[0][0]
 if sources.get('legacy_moderation'):
  for index,row in enumerate(json.loads((root/sources['legacy_moderation']).read_text()),1):
   model=row['model']
   if 'image_moderation' in models.get(model,{}).get('tasks',{}) or model in {m['model'] for m in moderation_rows}:continue
   if row['status']!='completed' or row['valid']!=row['total']:continue
   add('image_moderation',model,1000+index,row,sources['legacy_moderation'])
   models[model]['tasks']['image_moderation'].update(ranking_tier='legacy_screening_not_comparable',current_rank=None)
 if sources.get('runtime_profiles'):
  overrides=json.loads((root/sources['runtime_profiles']).read_text())
  for override in overrides['profiles']:
   model,task=override['model'],override['task']
   if override['status']!='passed' or override['digest']!=models[model]['tested_digest']:raise ValueError('Unverified runtime profile')
   meta=models[model]['tasks'][task]
   if override.get('tenant'):
    meta.setdefault('tenant_profiles',{})[override['tenant']]={**meta['profile'],**override['profile']}
    meta.setdefault('tenant_profile_evidence',{})[override['tenant']]=sources['runtime_profiles']
   else:
    meta['benchmark_profile']=dict(meta['profile'])
    meta['profile'].update(override['profile'])
    meta['profile_evidence']=sources['runtime_profiles']
 payload={'version':'ranked-model-policy.v1','selection':'first model in each independent task ranking; no silent lower-ranked fallback',
          'scope_notes':{'text_chat':'English structured-task ranking is the current text proxy; not a broad chat or non-English certification.','image_recognition':'Small controlled still-image ranking, timing tie-breaks descriptive only.','image_moderation':'Rank by positive detections, known correct decisions, false positives then latency; no standalone safety certification.'},
          'sources':evidence,'defaults':defaults,'models':models}
 if ranked.get('image') and ranked['image'][0].get('benchmark_version')=='vision-evaluation.v1':payload['scope_notes']['image_recognition']='Broader actual-service public-image cohort; cohort-specific object/OCR readiness, not general accuracy. Historical screening is explicit-only and not comparable.'
 if use_macro:payload['scope_notes']['image_moderation']='Broader nine-category human-review assistance ranking by macro F2; invalid/abstained positives count as missed detection. Sparse positives and no standalone safety certification.'
 if sources.get('runtime_profiles'):
  minimums=overrides.get('tenant_context_minimums',{})
  for tenant,tasks in minimums.items():
   for task,minimum in tasks.items():
    if not isinstance(minimum,int) or minimum<1:raise ValueError('Invalid required context')
    profile=models[defaults[task]]['tasks'][task].get('tenant_profiles',{}).get(tenant,{})
    if profile.get('num_ctx',0)<minimum:raise ValueError('Current ranking winner lacks verified context for '+tenant)
  payload['tenant_context_minimums']=minimums
 payload['policy_id']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
 return payload
if __name__=='__main__':
 parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--write',action='store_true');group.add_argument('--check',action='store_true');args=parser.parse_args();policy=build();target=ROOT/'config/model-policy.json';content=json.dumps(policy,indent=2)+'\n'
 if args.write:
  tmp=target.with_suffix('.tmp');tmp.write_text(content);tmp.replace(target)
 elif not target.exists() or target.read_text()!=content:raise SystemExit('Model policy is stale. Regenerate after reviewing ranking evidence.')
 rows=sorted(((name,entry['tasks']['image_moderation']) for name,entry in policy['models'].items() if 'image_moderation' in entry['tasks']),key=lambda x:x[1]['rank'])
 current=[row for row in rows if row[1].get('ranking_tier')!='legacy_screening_not_comparable'];legacy=[row for row in rows if row[1].get('ranking_tier')=='legacy_screening_not_comparable']
 if current and 'macro_f2' in current[0][1]['metrics']:
  lines=['# Moderation model ranking','','Current ranking uses the [broader nine-category evaluation](../vision-evaluation/REPORT.md). This is human-review assistance, never automatic approval/rejection.','','Order: equal-category macro F2, specificity, valid-response rate, then latency. Invalid/abstained positive references count as missed detection. Sparse positives, unknown references and per-category recall intervals remain visible. General images and non-English are separate.','','| Rank | Model | Macro F2 | Macro recall | Macro specificity | Valid responses | Median seconds |','| --- | --- | --- | --- | --- | --- | --- |']
  for name,entry in current:
   m=entry['metrics'];lines.append(f"| {entry['rank']} | {name} | {m['macro_f2']:.4f} | {m['macro_detection_recall']:.4f} | {m['macro_specificity']:.4f} | {m['valid']}/{m['total']} | {m['median_seconds']:.2f} |")
  if legacy:
   lines+=['','Historical screening alternatives are explicit-only and not numerically comparable to this cohort:']
   for name,entry in legacy:lines.append('- '+name+' ([evidence](../../'+entry['evidence']+')).')
 else:
  lines=['# Moderation model ranking','','Independent human-review-assistance ranking on the 25-image screening test. This is not automatic moderation approval. Per-category failures remain in [the full report](../moderation/REPORT.md).','','Order: positive detections, known correct decisions, false positives, then median latency. Unknown/review is not a correct negative. General-image and non-English scores do not enter this ranking.','','| Rank | Model | Positive detections | Known correct | False positives | Median seconds |','| --- | --- | --- | --- | --- | --- |']
  for name,entry in rows:
   m=entry['metrics'];lines.append(f"| {entry['rank']} | {name} | {m['true_positives']} | {m['known_correct']} | {m['false_positives']} | {m['median_seconds']:.2f} |")
 ranking=ROOT/'benchmarks/rankings/MODERATION.md';ranking_content='\n'.join(lines)+'\n'
 if args.write:ranking.write_text(ranking_content)
 elif not ranking.exists() or ranking.read_text()!=ranking_content:raise SystemExit('Moderation ranking report is stale')
 print(json.dumps({'policy_id':policy['policy_id'],'defaults':policy['defaults'],'tested_models':len(policy['models'])}))
