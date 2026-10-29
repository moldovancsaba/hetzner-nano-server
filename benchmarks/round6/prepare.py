"""Freeze new candidate metadata and complete existing research suites before inference."""
import hashlib,json,shutil,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parent.parent;PRIVATE=REPO/'private/round6';PRIVATE.mkdir(parents=True,exist_ok=True)
candidates=[
 {'model':'hf.co/LiquidAI/LFM2-1.2B-GGUF:LFM2-1.2B-Q4_K_M.gguf','task':'text','repo':'LiquidAI/LFM2-1.2B-GGUF','upstream':'LiquidAI/LFM2-1.2B','filename':'LFM2-1.2B-Q4_K_M.gguf'},
 {'model':'hf.co/allenai/OLMo-2-0425-1B-Instruct-GGUF:Q4_K_M','task':'text','repo':'allenai/OLMo-2-0425-1B-Instruct-GGUF','upstream':'allenai/OLMo-2-0425-1B-Instruct','filename':'OLMo-2-0425-1B-Instruct-Q4_K_M.gguf'},
 {'model':'hf.co/ggml-org/SmolVLM2-256M-Video-Instruct-GGUF:Q8_0','task':'vision','repo':'ggml-org/SmolVLM2-256M-Video-Instruct-GGUF','upstream':'HuggingFaceTB/SmolVLM2-256M-Video-Instruct','filename':'SmolVLM2-256M-Video-Instruct-Q8_0.gguf'},
 {'model':'hf.co/bartowski/OpenGVLab_InternVL3_5-1B-GGUF:Q4_K_M','task':'vision','repo':'bartowski/OpenGVLab_InternVL3_5-1B-GGUF','upstream':'OpenGVLab/InternVL3_5-1B','filename':'OpenGVLab_InternVL3_5-1B-Q4_K_M.gguf'}]
known={x['model'].lower() for x in json.loads((REPO/'config/tested-models.json').read_text())['models']};sources=[]
for c in candidates:
 assert c['model'].lower() not in known
 d=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+c['repo']+'?blobs=true'));up=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+c['upstream']));files=[x for x in d['siblings'] if x['rfilename']==c['filename'] or 'mmproj' in x['rfilename']];primary=next(x for x in files if x['rfilename']==c['filename'])
 projectors=[x for x in files if 'mmproj' in x['rfilename']];aux=max((x.get('size',0) for x in projectors),default=0)
 c.update(expected_primary_bytes=primary['size'],maximum_projector_bytes=aux,revision=d['sha'],upstream_revision=up['sha'],license=up.get('cardData',{}).get('license'),source='https://huggingface.co/'+c['upstream'])
 sources.append({'model':c['model'],'repo':c['repo'],'revision':d['sha'],'upstream_revision':up['sha'],'license':c['license'],'artifacts':[{'file':x['rfilename'],'bytes':x.get('size'),'sha256':x.get('lfs',{}).get('sha256')} for x in files]})
plan={'version':'round6.v1','scope':'Four new exact checkpoints; English 14 structured checks + native tool call; text candidates separately tested on 35 Hungarian cases. Vision 32 recognition +9 robustness +8 counting +41 moderation each, subject only to explicit safety/resource stops. No video or twelve-reason coverage claim.','settings':{'memory_mib':2800,'hard_disk_floor_gib':4,'disk_staging_margin_bytes':100*1024**2},'candidates':candidates,'image_profile':{'max_image_edge':640,'num_ctx':4096,'num_batch':16,'think':False},'hungarian_profile':{'num_ctx':2048,'num_batch':16,'num_predict':192,'temperature':0},'stopping':'Stop on OOM, resource/timeout uncertainty, or three consecutive technical failures; retain partial evidence as failed, never completed. Wrong semantic answers do not stop the suite.'}
(ROOT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');(ROOT/'source-metadata.json').write_text(json.dumps(sources,indent=2)+'\n')
for src,dst in [('benchmarks/round5/recognition-manifest.json','recognition-manifest.json'),('benchmarks/vision-evaluation/moderation-manifest.json','moderation-manifest.json'),('benchmarks/non-english/hu-round2/fixtures.json','hu-fixtures.json')]:shutil.copyfile(REPO/src,ROOT/dst)
images=PRIVATE/'inputs';images.mkdir(exist_ok=True);paths={}
rec=json.loads((ROOT/'recognition-manifest.json').read_text());mod=json.loads((ROOT/'moderation-manifest.json').read_text())
for c in rec['recognition']+rec['robustness']+mod['cases']+mod.get('robustness',[]):
 source=REPO/'private/vision-evaluation/images'/c['file']
 if not source.exists():
  for directory in [REPO/'benchmarks/round5/inputs',REPO/'private/round5/inputs']:
   if (directory/c['file']).exists():source=directory/c['file'];break
 assert source.exists(),str(source)
 assert hashlib.sha256(source.read_bytes()).hexdigest()==c['sha256'],c['id']
 shutil.copyfile(source,images/c['file']);paths[c['file']]=c['sha256']
(ROOT/'input-audit.json').write_text(json.dumps({'count':len(paths),'files':paths,'scope':'Frozen approved research evaluation inputs only; images excluded from Git.'},indent=2)+'\n')
print('Prepared',len(candidates),'new candidates and',len(paths),'verified image files')
