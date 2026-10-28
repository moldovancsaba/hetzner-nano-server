"""Retain the exact official text weights without an unused vision projector."""
import json,pathlib,re,subprocess,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
ns={'__file__':str(ROOT/'pull_fallback.py')};exec((ROOT/'pull_fallback.py').read_text().split('held=None;stop=')[0],ns);lease=ns['lease']
def native(path,data=None):
 req=urllib.request.Request('http://127.0.0.1:11434'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
held=None;source='qwen3.5:2b-q4_K_M';target='hungarian-qwen35-2b:q4_k_m'
try:
 for _ in range(450):
  try:held=lease('acquire')['lease'];break
  except urllib.error.HTTPError as e:
   if e.code!=409:raise
   time.sleep(2)
 assert held,'No idle lease'
 show=native('/api/show',{'model':source})
 blob='sha256:'+re.search(r'FROM .*sha256-([a-f0-9]{64})',show['modelfile']).group(1)
 body={'model':target,'files':{'model.gguf':blob},'template':show['template'],'license':show.get('license',''),'stream':False,'parameters':{'num_ctx':2048,'num_batch':32,'temperature':0}}
 for key in ['renderer','parser']:
  match=re.search(r'^'+key.upper()+r'\s+(\S+)',show['modelfile'],re.M)
  if match:body[key]=match.group(1)
 assert native('/api/create',body)['status']=='success'
 for m in native('/api/ps')['models']:native('/api/generate',{'model':m['name'],'keep_alive':0})
 result=native('/api/chat',{'model':target,'messages':[{'role':'user','content':'Írd azt: KÉSZ.'}],'think':False,'stream':False,'options':{'num_ctx':2048,'num_batch':32,'num_predict':16,'temperature':0}})
 assert result.get('message',{}).get('content') and result.get('done')
 native('/api/generate',{'model':target,'keep_alive':0})
 with urllib.request.urlopen('https://registry.ollama.ai/v2/library/qwen3.5/manifests/2b-q4_K_M',timeout=20) as r:manifest=json.load(r)
 assert any(layer['digest']==blob and layer['mediaType'].endswith('.model') for layer in manifest['layers'])
 source_tag=next(m for m in native('/api/tags')['models'] if m['name']==source)
 subprocess.run(['docker','exec','narimato-ollama','ollama','rm',source],check=True,capture_output=True)
 audit={'source':source,'source_manifest_digest':source_tag['digest'],'model':target,'text_weight_blob':blob,'template_preserved':True,'renderer':body.get('renderer'),'parser':body.get('parser'),'text_smoke_completed':True,'source_package_removed':True,'reason':'Hungarian text only: remove unused projector; evaluate this exact derivative manifest in full.'}
 (ROOT/'text-only.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit))
finally:
 if held:lease('release',held)
