import pathlib,json,subprocess,time,datetime,shutil,urllib.request
from fixtures import call,trim,unload,cases
ROOT=pathlib.Path(__file__).parent
raw=json.loads((ROOT/'results.json').read_text());eligible=[]
for m in raw['text']:
 if ('LFM2.5-2.6B' in m['model'] or m['model']=='deepseek-r1:1.5b') and any(t.get('done_reason')=='length' and not t.get('response','').strip() for t in m['tests']):eligible.append(m['model'])
report={'scope':'Separate English reasoning smoke checks; NOT part of short-output accuracy ranking','max_output_tokens':1024,'context':2048,'num_batch':32,'think':True,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'models':[],'source':'https://huggingface.co/LiquidAI/LFM2.5-2.6B#chat-template','note':'One case per selected budget-limited model. Reasoning text is not saved, only presence/length; larger budget result is not comparable with the 180-token suite.'}
def save():(ROOT/'reasoning-check.json').write_text(json.dumps(report,indent=2)+'\n')
with urllib.request.urlopen('http://127.0.0.1:11434/api/tags') as response:initial=json.load(response)
original={m['name'].lower() for m in initial['models']}
previous='qwen3:1.7b'
try:
 for model in eligible:
  print('REASONING CHECK',model,flush=True);entry={'model':model};report['models'].append(entry);new=model.lower() not in original
  try:
   unload(previous);previous=model
   if shutil.disk_usage('/').free<4*1024**3+2600*1024**2:entry['status']='disk_reserve_skip';continue
   with (ROOT/('reasoning-pull-'+str(len(report['models']))+'.log')).open('w') as log:pull=subprocess.run(['docker','exec','narimato-ollama','ollama','pull',model],stdout=log,stderr=subprocess.STDOUT,timeout=300)
   if pull.returncode:entry['status']='pull_failed';continue
   name,prompt,validate=cases[0]
   r=call('/api/chat',{'model':model,'messages':[{'role':'user','content':prompt}],'think':True,'format':'json','stream':False,'options':{'num_ctx':2048,'num_batch':32,'num_predict':1024,'temperature':0}},180)
   msg=r.get('data',{}).get('message',{});text=msg.get('content','');valid=False;correct=False
   try:d=json.loads(text);valid=True;correct=bool(validate(d))
   except Exception:pass
   entry.update({'status':'completed','case':name,**trim(r),'response':text,'json_valid':valid,'correct':correct,'thinking_present':bool(msg.get('thinking')),'thinking_characters':len(msg.get('thinking',''))})
  except Exception as e:entry['status']='runner_exception';entry['error_type']=type(e).__name__
  finally:
   unload(model)
   if new:entry['new_package_removed']=subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model],capture_output=True,timeout=45).returncode==0
   save();print('REASONING DONE',model,entry.get('correct'),entry.get('seconds'),flush=True)
finally:
 unload(previous);r=call('/api/generate',{'model':'qwen3:1.7b','prompt':'Reply READY.','think':False,'stream':False,'keep_alive':'30m','options':{'num_ctx':2048,'num_batch':32,'num_predict':12}},120);report['restored_original']=trim(r);report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();print('REASONING RESTORED ORIGINAL',flush=True)
