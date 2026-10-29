"""Resume saved cases with independent module stops; never repeat a recorded case."""
import json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parent
source=(ROOT/'run.py').read_text().split('timer=subprocess.run',1)[0];ns={'__file__':str(ROOT/'run.py'),'__name__':'round6_resume'};exec(compile(source,'round6_shared','exec'),ns)
report=json.loads((ROOT/'results.json').read_text());ns['report']=report;ns['ns']['report']=report;save=ns['save'];guarded=ns['guarded'];unload=ns['unload'];memory=ns['memory']
report.setdefault('continuations',[]).append({'at':ns['now'](),'reason':'Checkpointed at an idle maintenance lease to make contract-failure stops independent per task and keep a bounded completion window. All recorded cases, frozen inputs, profiles and failures preserved; only previously unattempted cases execute.'});report.pop('finished_utc',None);save()
timer=report.get('cleanup_timer_was_active',False)
def cleanup(model):
 guarded(unload)
 result=guarded(lambda:subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model],capture_output=True,timeout=60))
 return result.returncode==0
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 # Checkpointed temporary vision weights must not occupy disk while finishing text.
 for m in report['models']:
  if m['task']=='vision' and any(t['name'].lower()==m['model'].lower() for t in ns['get']('/api/tags')['models']):m['temporary_weights_removed']=cleanup(m['model']);save()
 for candidate in ns['plan']['candidates']:
  model=candidate['model'];m=next((x for x in report['models'] if x['model']==model),None)
  if m is None:m={**candidate,'status':'preparing','started_utc':ns['now']()};report['models'].append(m)
  if m['task']=='text' and len(m.get('hungarian',[]))==35:continue
  try:
   tag,meta=guarded(lambda:ns['prepare'](candidate))
   if m.get('tag'):assert tag['digest']==m['tag']['digest'],'Artifact changed; do not mix outputs'
   m.update(tag=tag,**meta);before=memory();m.setdefault('prior_errors',[]).append({'status':m['status'],'error':m.pop('error',None),'error_type':m.pop('error_type',None)});m['status']='running';save()
   if m['task']=='text':
    m.setdefault('hungarian',[]);done={t['id'] for t in m['hungarian']}
    for case in ns['hu']['cases']:
     if case['id'] in done:continue
     row=guarded(lambda c=case:ns['hu_case'](model,c));m['hungarian'].append(row);save();print('HU-REMAINDER',model,case['id'],row['ok'],flush=True)
     if memory()['events'].get('oom_kill',0)>before['events'].get('oom_kill',0):raise RuntimeError('OOM; stop candidate')
     if not row['ok'] and row.get('error_type') in ['TimeoutError','URLError','OSError']:raise RuntimeError('Upstream uncertain; stop candidate')
     if len(m['hungarian'])>=3 and all(not t['ok'] for t in m['hungarian'][-3:]):raise RuntimeError('Three consecutive Hungarian technical failures')
    m['hungarian_status']='all_cases_attempted_with_errors' if any(not t['ok'] for t in m['hungarian']) else 'completed'
   else:
    fields=[('tests',ns['manifest']['recognition'],'image_recognition'),('robustness',ns['manifest']['robustness'],'image_recognition'),('counts',[c for c in ns['manifest']['recognition'] if c.get('count_probe')],'count'),('moderation',ns['moderation']['cases'],'image_moderation'),('moderation_robustness',ns['moderation'].get('robustness',[]),'image_moderation')]
    for field,cases,task in fields:
     m.setdefault(field,[]);done={t['id'] for t in m[field]}
     # A repeated contract failure stops that module only. Other tasks still run.
     if field=='robustness' and m.get('tests_status')=='stopped_contract_failure':m[field+'_status']='not_run_primary_contract_failed';continue
     if len(m[field])>=3 and all(t['status']=='failed' for t in m[field][-3:]):m[field+'_status']='stopped_contract_failure';continue
     for case in cases:
      if case['id'] in done:continue
      row=guarded(lambda c=case,t=task:ns['image_case'](model,c,t));m[field].append(row);save();print('CASE',model,field,case['id'],row['status'],row['seconds'],flush=True)
      if row['oom_kill_delta']:raise RuntimeError('OOM; stop candidate')
      if len(m[field])>=3 and all(t['status']=='failed' for t in m[field][-3:]):m[field+'_status']='stopped_contract_failure';break
     else:m[field+'_status']='completed'
   m['oom_kill_delta']=memory()['events'].get('oom_kill',0)-before['events'].get('oom_kill',0)
   m['status']='completed' if m['task']=='text' and m.get('hungarian_status')=='completed' or m['task']=='vision' and all(m.get(k+'_status')=='completed' for k in ['tests','robustness','counts','moderation','moderation_robustness']) else 'completed_with_module_failures'
  except Exception as e:m.update(status='failed',error_type=type(e).__name__,error=str(e)[:800])
  finally:
   m['temporary_weights_removed']=cleanup(model);m['finished_utc']=ns['now']();save();print('DONE',model,m['status'],flush=True)
finally:
 try:
  def restore():
   unload();return ns['infer'](ns['payload']('granite4:1b-h','Reply READY.',options={'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}))
  report['restore']=guarded(restore)
 finally:
  if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
  report['finished_utc']=ns['now']();save();print('FINISHED',flush=True)
