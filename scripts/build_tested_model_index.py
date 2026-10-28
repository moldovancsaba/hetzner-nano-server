"""Produce a metadata-only index of past model attempts, including failures."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=['benchmarks/capabilities/results.json','benchmarks/round2/results.json','benchmarks/round2/supplement-text.json','benchmarks/round2/vision-retries.json','benchmarks/round3/results.json','benchmarks/round3/results-extra.json','benchmarks/round3/reasoning-check.json','benchmarks/moderation/results.json','benchmarks/round4/results.json','benchmarks/vision-evaluation/recognition-results.json','benchmarks/vision-evaluation/moderation-results.json']
SOURCES.append('benchmarks/round5/results.json')
SOURCES.append('benchmarks/non-english/hu-round1/results.json')
SOURCES.append('benchmarks/non-english/hu-round2/results.json')
SOURCES.append('benchmarks/camera-specialists/results.json')
def canonical(name):
 name=name.lower().removeprefix('hf.co/').removeprefix('https://huggingface.co/')
 if '/' in name:name=name.rsplit('/',1)[-1].split(':')[0]
 name=re.sub(r'(?:instruct|gguf|instruction|\bit\b)','',name)
 return re.sub(r'[^a-z0-9]','',name)
def build():
 records={}
 def walk(value,source):
  if isinstance(value,dict):
   model=value.get('model')
   if isinstance(model,str) and (':' in model or '/' in model) and ('status' in value or 'tests' in value):
    row=records.setdefault(model,{'model':model,'canonical':canonical(model),'evidence':[],'outcomes':[]})
    if source not in row['evidence']:row['evidence'].append(source)
    if value.get('status') and value['status'] not in row['outcomes']:row['outcomes'].append(value['status'])
    if isinstance(value.get('tag'),dict) and value['tag'].get('digest'):row['tested_digest']=value['tag']['digest']
   for child in value.values():walk(child,source)
  elif isinstance(value,list):
   for child in value:walk(child,source)
 for source in SOURCES:walk(json.loads((ROOT/source).read_text()),source)
 policy=json.loads((ROOT/'config/model-policy.json').read_text())
 for name,entry in policy['models'].items():
  row=records.setdefault(name,{'model':name,'canonical':canonical(name),'evidence':[],'outcomes':[]});row['tested_digest']=entry['tested_digest'];row['ranked_tasks']=list(entry['tasks'])
 decisions=json.loads((ROOT/'config/model-decisions.json').read_text())['decisions']
 for name,d in decisions.items():records.setdefault(name,{'model':name,'canonical':canonical(name),'evidence':[],'outcomes':[]})['decision']=d
 return {'version':'tested-model-index.v1','models':list(records.values()),'source_hashes':{source:hashlib.sha256((ROOT/source).read_bytes()).hexdigest() for source in SOURCES}}
if __name__=='__main__':
 out=build();(ROOT/'config/tested-models.json').write_text(json.dumps(out,indent=2)+'\n');print('Indexed',len(out['models']),'model variants, including failed attempts; no inputs/answers copied.')
