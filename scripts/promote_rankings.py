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
 paths=list(dict.fromkeys([sources['english_and_images'],sources['moderation'],sources['moderation_raw']]+sources['digest_evidence']+runtime_paths))
 for name in paths:
  data=(root/name).read_bytes();evidence.append({'path':name,'sha256':hashlib.sha256(data).hexdigest()});walk(json.loads(data))
 ranked=json.loads((root/sources['english_and_images']).read_text());models={};defaults={}
 def add(task,model,rank,metrics,source,edge=640):
  digest=digests.get(model.lower())
  if not digest:raise ValueError('No tested artifact digest for '+model)
  entry=models.setdefault(model,{'id':model,'tested_digest':digest,'tasks':{}})
  entry['tasks'][task]={'rank':rank,'metrics':metrics,'evidence':source,'profile':{'max_image_edge':edge,'num_ctx':2048,'num_batch':32}}
 for task,field in [('text_chat','english'),('image_recognition','image')]:
  rows=ranked[field]
  if not rows:raise ValueError('No ranking for '+task)
  for rank,row in enumerate(rows,1):add(task,row['model'],rank,row,sources['english_and_images'],row.get('max_image_dimension',640))
  defaults[task]=rows[0]['model']
 raw=json.loads((root/sources['moderation_raw']).read_text());moderation=[]
 for row in json.loads((root/sources['moderation']).read_text()):
  if row['status']!='completed' or row['valid']!=row['total'] or row['total']<1:continue
  cats=row['categories'];tests=next(m['tests'] for m in raw['models'] if m['model']==row['model'])
  metrics={'true_positives':sum(c['tp'] for c in cats.values()),'known_correct':sum(c['tp']+c['tn'] for c in cats.values()),'false_positives':sum(c['fp'] for c in cats.values()),'median_seconds':statistics.median(t['seconds'] for t in tests),'categories':cats}
  moderation.append((row['model'],metrics))
 moderation.sort(key=lambda pair:(-pair[1]['true_positives'],-pair[1]['known_correct'],pair[1]['false_positives'],pair[1]['median_seconds'],pair[0]))
 if not moderation:raise ValueError('No complete moderation evidence')
 for rank,(model,metrics) in enumerate(moderation,1):add('image_moderation',model,rank,metrics,sources['moderation'])
 defaults['image_moderation']=moderation[0][0]
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
 lines=['# Moderation model ranking','','Independent human-review-assistance ranking on the 25-image screening test. This is not automatic moderation approval. Per-category failures remain in [the full report](../moderation/REPORT.md).','','Order: positive detections, known correct decisions, false positives, then median latency. Unknown/review is not a correct negative. General-image and non-English scores do not enter this ranking.','','| Rank | Model | Positive detections | Known correct | False positives | Median seconds |','| --- | --- | --- | --- | --- | --- |']
 for name,entry in rows:
  m=entry['metrics'];lines.append(f"| {entry['rank']} | {name} | {m['true_positives']} | {m['known_correct']} | {m['false_positives']} | {m['median_seconds']:.2f} |")
 ranking=ROOT/'benchmarks/rankings/MODERATION.md';ranking_content='\n'.join(lines)+'\n'
 if args.write:ranking.write_text(ranking_content)
 elif not ranking.exists() or ranking.read_text()!=ranking_content:raise SystemExit('Moderation ranking report is stale')
 print(json.dumps({'policy_id':policy['policy_id'],'defaults':policy['defaults'],'tested_models':len(policy['models'])}))
