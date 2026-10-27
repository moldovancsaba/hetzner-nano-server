"""Bounded public metadata discovery; never downloads weights or executes remote text."""
import argparse,datetime,gzip,hashlib,json,re,sqlite3,time,urllib.parse,urllib.request,shutil
from pathlib import Path

UA='HetznerNanoModelDiscovery/1.0 (metadata-only research; github.com/moldovancsaba/hetzner-nano-server)'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def canonical(name):
 name=name.lower().removeprefix('hf.co/')
 if '/' in name:name=name.rsplit('/',1)[-1].split(':')[0]
 name=re.sub(r'(?:instruct|gguf|instruction|\bit\b)','',name)
 return re.sub(r'[^a-z0-9]','',name)
def clean(value,n=240):return re.sub(r'[\x00-\x1f]','',str(value or ''))[:n]
def parameters(name,metadata=None):
 total=(metadata or {}).get('safetensors',{}).get('total')
 if isinstance(total,(int,float)) and total>0:return round(total/1e9,4),'safetensors_total'
 values=re.findall(r'(?<![a-z0-9])(\d+(?:\.\d+)?)\s*([bm])(?=[^a-z0-9]|$)',name.lower())
 if values:
  number,unit=values[-1];return float(number)/(1000 if unit=='m' else 1),'name_estimate'
 return None,'unknown'
def hf(row,trusted):
 name=clean(row.get('id') or row.get('modelId'));author=name.split('/')[0];tags=[clean(t,80) for t in row.get('tags',[])[:40]];params,kind=parameters(name,row)
 card=row.get('cardData') or {};license=card.get('license') or next((tag.split(':',1)[1] for tag in tags if tag.startswith('license:')),None)
 if isinstance(license,list):license=[clean(x,80) for x in license[:5]]
 elif license:license=clean(license,80)
 return {'key':'hf:'+name,'source':'huggingface','id':name,'url':'https://huggingface.co/'+urllib.parse.quote(name,safe='/'),
         'revision':clean(row.get('sha'),80),'modified':clean(row.get('lastModified'),80),'pipeline':clean(row.get('pipeline_tag'),80),
         'tags':tags,'license':license,'parameter_billions':params,'parameter_basis':kind,'publisher_verified_by_allowlist':author.lower() in {a.lower() for a in trusted},
         'weight_format':'gguf' if 'gguf' in [t.lower() for t in tags] or 'gguf' in name.lower() else 'unknown','gated':bool(row.get('gated')),'downloads':row.get('downloads',0),'likes':row.get('likes',0)}
def router(row):
 name=clean(row.get('id'));params,kind=parameters(name);architecture=row.get('architecture') or {}
 return {'key':'openrouter:'+name,'source':'openrouter','id':name,'url':'https://openrouter.ai/'+urllib.parse.quote(name,safe='/'),
         'revision':clean(row.get('created'),80),'parameter_billions':params,'parameter_basis':kind,
         'input_modalities':architecture.get('input_modalities',[]),'context_length':row.get('context_length'),
         'supported_parameters':row.get('supported_parameters',[])[:30],'weight_format':'unverified','license':None,
         'local_runtime_verified':False,'publisher_verified_by_allowlist':False,'hugging_face_id':clean(row.get('hugging_face_id'),240)}
def classify(row,known):
 matches=[m for m in known if m['canonical']==canonical(row['id'])]
 row=dict(row);row['prior_evidence']=[{'model':m['model'],'evidence':m.get('evidence',[]),'outcomes':m.get('outcomes',[]),'decision':m.get('decision')} for m in matches]
 row['test_status']='known_model_family_verify_revision' if matches else 'not_in_test_index'
 size=row.get('parameter_billions');score=0;reasons=[]
 if size is None:reasons.append('Parameter/weight size unknown; inspect artifact before eligibility test')
 elif size<=1.7:score+=40;reasons.append('Small parameter estimate is promising for the CPU/RAM budget')
 elif size<=3:score+=15;reasons.append('Borderline parameter estimate; exact quantization/projector/KV overhead must fit')
 else:score-=100;reasons.append('Parameter estimate exceeds the current small-model screening ceiling')
 if row.get('publisher_verified_by_allowlist'):score+=15
 if row.get('weight_format')=='gguf':score+=15
 else:reasons.append('Local GGUF/Ollama artifact not verified')
 if row.get('license'):score+=5
 else:reasons.append('License/usage rights need verification')
 modalities=row.get('input_modalities',[]);pipeline=row.get('pipeline','')
 row['possible_workstreams']=['image_recognition','image_moderation'] if 'image' in modalities or pipeline in ['image-text-to-text','image-to-text'] or 'vision' in row.get('tags',[]) or re.search(r'(?:vlm|vision|\bvl\b)',row['id'],re.I) else ['english_text']
 if pipeline in {'automatic-speech-recognition','text-to-speech','audio-classification','feature-extraction','sentence-similarity','time-series-forecasting','fill-mask','token-classification','text-classification'} or (not pipeline and re.search(r'(?:speech|whisper|timestral|time.series|embedding|turboctc|text.to.speech)',row['id'],re.I)):
  score-=100;row['possible_workstreams']=['out_of_scope'];reasons.append('Not a text-generation or visual-understanding candidate for current jobs')
 if row['source']=='openrouter':score-=15;reasons.append('Hosted listing is discovery evidence, not proof of downloadable local weights')
 if matches:score-=100;reasons.append('Already-known family: do not repeat unchanged tests; verify revision or changed runtime first')
 if row.get('gated'):score-=10;reasons.append('Gated download requires operator review')
 row['screening_score']=score;row['screening_reasons']=reasons;row['runtime_eligibility']='unverified';row['language_approval']='none'
 return row

def fetch(url,limit):
 if urllib.parse.urlsplit(url).scheme!='https' or urllib.parse.urlsplit(url).hostname not in {'huggingface.co','openrouter.ai','ollama.com','api.github.com'}:raise ValueError('Source host not allowlisted')
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json, text/html;q=0.8'})
 with urllib.request.urlopen(req,timeout=20) as response:
  raw=response.read(limit+1)
 if len(raw)>limit:raise ValueError('Source response exceeds metadata budget')
 return raw

def collect(state,config,tested):
 state.mkdir(parents=True,exist_ok=True,mode=0o700);snapshots=state/'snapshots';snapshots.mkdir(exist_ok=True,mode=0o700)
 known=tested['models'];sources=[];records={};runtime=[]
 def source(name,url,parser):
  start=time.monotonic()
  try:
   raw=fetch(url,config['max_response_bytes']);items=parser(raw)
   for row in items:records[row['key']]=classify(row,known)
   sources.append({'source':name,'url':url,'status':'ok','records':len(items),'seconds':round(time.monotonic()-start,2),'response_sha256':hashlib.sha256(raw).hexdigest()})
  except Exception as exc:sources.append({'source':name,'url':url,'status':'error','error_type':type(exc).__name__,'http_status':getattr(exc,'code',None),'seconds':round(time.monotonic()-start,2)})
 for author in config['trusted_hf_authors']:
  query=urllib.parse.urlencode({'author':author,'sort':'lastModified','direction':-1,'limit':config['hf_author_limit'],'full':'true'})
  source('huggingface-publisher:'+author,'https://huggingface.co/api/models?'+query,lambda raw:[hf(r,config['trusted_hf_authors']) for r in json.loads(raw)])
 for params in [{'filter':'gguf','limit':config['hf_recent_gguf_limit']},{'pipeline_tag':'image-text-to-text','limit':config['hf_recent_vision_limit']}]:
  query=urllib.parse.urlencode({'sort':'lastModified','direction':-1,'full':'true',**params})
  source('huggingface-recent','https://huggingface.co/api/models?'+query,lambda raw:[hf(r,config['trusted_hf_authors']) for r in json.loads(raw)])
 source('openrouter','https://openrouter.ai/api/v1/models',lambda raw:[router(r) for r in json.loads(raw)['data']])
 def ollama(raw):
  names=list(dict.fromkeys(re.findall(r'href="/library/([a-zA-Z0-9_.-]+)"',raw.decode(errors='replace'))))[:60]
  return [{'key':'ollama:'+name,'id':name,'source':'ollama','url':'https://ollama.com/library/'+name,'revision':'','parameter_billions':None,'parameter_basis':'unknown','license':None,'weight_format':'ollama_family_listing','publisher_verified_by_allowlist':True} for name in names]
 source('ollama-library','https://ollama.com/library?sort=newest',ollama)
 for repo in ['ollama/ollama','ggml-org/llama.cpp']:
  def release(raw,repo=repo):
   data=json.loads(raw);runtime.append({'repository':repo,'tag':clean(data.get('tag_name'),120),'published_at':clean(data.get('published_at'),80),'url':clean(data.get('html_url'),300)});return []
  source('runtime-release:'+repo,'https://api.github.com/repos/'+repo+'/releases/latest',release)
 now=utc();db=sqlite3.connect(state/'registry.sqlite3');db.execute('CREATE TABLE IF NOT EXISTS models (key TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT, revision TEXT, record_json TEXT)')
 changes=[]
 for key,row in records.items():
  old=db.execute('SELECT first_seen,revision,record_json FROM models WHERE key=?',(key,)).fetchone();row['first_seen_utc']=old[0] if old else now;row['last_seen_utc']=now
  if old and row.get('revision') and row['revision']!=old[1]:changes.append({'key':key,'previous':old[1],'current':row['revision']})
  db.execute('INSERT OR REPLACE INTO models VALUES (?,?,?,?,?)',(key,row['first_seen_utc'],now,row.get('revision',''),json.dumps(row)))
 db.commit()
 # Keep the accumulated registry bounded; never delete known tested/declined evidence stored separately in config/tested-models.json.
 count=db.execute('SELECT COUNT(*) FROM models').fetchone()[0]
 if count>config['max_registry_records']:
  db.execute('DELETE FROM models WHERE key IN (SELECT key FROM models ORDER BY last_seen ASC LIMIT ?)',(count-config['max_registry_records'],));db.commit()
 shortlist=sorted((row for row in records.values() if row['test_status']=='not_in_test_index' and row['screening_score']>=30),key=lambda row:(-row['screening_score'],-row.get('likes',0),row['key']))[:config['shortlist_limit']]
 successful=sum(s['status']=='ok' for s in sources);report={'generated_utc':now,'status':'ok' if successful==len(sources) else 'degraded' if successful else 'failed','sources':sources,'observed_models':len(records),'registry_models':db.execute('SELECT COUNT(*) FROM models').fetchone()[0],'revision_changes':changes,'runtime_releases':runtime,'shortlist':shortlist,'limitations':['Scores are metadata heuristics, not model quality or RAM benchmarks.','Bounded discovery feeds are not exhaustive; popularity and context length do not prove local suitability.','Already-tested family matching is heuristic; inspect model variant, revision, projector and quantization before testing.','No weights downloaded, no generation performed, no production requests captured.']};db.close()
 report['storage']={'disk_free_gib':round(shutil.disk_usage('/').free/1024**3,2),'automatic_weight_deletion':False}
 try:
  req=urllib.request.Request('http://127.0.0.1:11434/api/tags')
  with urllib.request.urlopen(req,timeout=5) as response:installed=json.load(response)['models']
  decisions={m['model'].lower():m.get('decision') for m in known if m.get('decision')}
  report['storage']['installed_models']=[{'name':m['name'],'digest':m.get('digest'),'size_bytes':m.get('size'),'decision':decisions.get(m['name'].lower())} for m in installed]
 except Exception:report['storage']['inventory_status']='unavailable'
 temporary=state/'latest.tmp';temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.replace(state/'latest.json')
 if successful:
  saved=state/'last-success.tmp';saved.write_text(json.dumps(report,indent=2)+'\n');saved.replace(state/'last-success.json')
 snapshot=snapshots/(now[:10]+'.json.gz')
 with gzip.open(snapshot,'wt') as handle:json.dump({'generated_utc':now,'records':list(records.values()),'sources':sources},handle)
 for path in snapshots.glob('*.json.gz'):
  if time.time()-path.stat().st_mtime>config['snapshot_days']*86400:path.unlink()
 paths=sorted(snapshots.glob('*.json.gz'),key=lambda p:p.stat().st_mtime)
 while len(paths)>1 and sum(p.stat().st_size for p in paths)>config['snapshot_budget_bytes']:paths.pop(0).unlink()
 return report
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--state-dir',type=Path,required=True);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--tested-index',type=Path,required=True);args=parser.parse_args()
 result=collect(args.state_dir,json.loads(args.config.read_text()),json.loads(args.tested_index.read_text()))
 print(json.dumps({'status':result['status'],'observed_models':result['observed_models'],'shortlist':len(result['shortlist']),'sources_ok':sum(s['status']=='ok' for s in result['sources']),'sources_total':len(result['sources'])}))
 if result['status']=='failed':raise SystemExit(1)
