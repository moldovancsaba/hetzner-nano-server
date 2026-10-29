"""Evaluate independent remaining image modules after a recognition-format stop."""
import json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parent
source=(ROOT/'run.py').read_text().split('timer=subprocess.run',1)[0];ns={'__file__':str(ROOT/'run.py'),'__name__':'round6_vision_completion'};exec(compile(source,'round6_shared','exec'),ns)
report=json.loads((ROOT/'results.json').read_text());ns['report']=report;ns['ns']['report']=report
report.setdefault('completion_events',[]).append({'at':ns['now'](),'reason':'Recognition-format failure must not prevent independent count/moderation evaluation. Run unattempted modules with the same frozen inputs/profile and retain the primary recognition stop; do not rerun failed recognition cases.'})
report.setdefault('prior_restorations',[]).append(report.pop('restore',None));report.pop('finished_utc',None)
guarded=ns['guarded'];save=ns['save'];unload=ns['unload'];timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 for m in report['models']:
  if m['task']!='vision':continue
  recognition_contract_stop=m.get('error')=='Three consecutive technical failures; stop candidate' and m.get('tests') and all(t.get('error_type')=='ValueError' and not t.get('oom_kill_delta',0) for t in m['tests'][-3:])
  if not recognition_contract_stop and m.get('status')!='completed':continue
  model=m['model'];candidate=next(c for c in ns['plan']['candidates'] if c['model']==model)
  try:
   tag,meta=guarded(lambda:ns['prepare'](candidate));assert tag['digest']==m['tag']['digest'],'Changed artifact'
   for field,cases,task in [('counts',[c for c in ns['manifest']['recognition'] if c.get('count_probe')],'count'),('moderation',ns['moderation']['cases'],'image_moderation'),('moderation_robustness',ns['moderation'].get('robustness',[]),'image_moderation')]:
    m.setdefault(field,[]);done={t['id'] for t in m[field]}
    for case in cases:
     if case['id'] in done:continue
     row=guarded(lambda c=case,t=task:ns['image_case'](model,c,t));m[field].append(row);save();print('INDEPENDENT',model,field,case['id'],row['status'],flush=True)
     if row['oom_kill_delta']:raise RuntimeError('OOM; stop')
     if len(m[field])>=3 and all(t['status']=='failed' for t in m[field][-3:]):m[field+'_status']='stopped_after_three_technical_failures';break
    else:m[field+'_status']='completed'
  except Exception as e:m.setdefault('independent_task_errors',[]).append({'error_type':type(e).__name__,'error':str(e)[:800]})
  finally:
   guarded(unload)
   if model.lower() not in ns['initial']:guarded(lambda:subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model],check=True,capture_output=True,timeout=60));m['temporary_weights_removed']=True
   save()
finally:
 try:
  def restore():
   unload();return ns['infer'](ns['payload']('granite4:1b-h','Reply READY.',options={'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}))
  report['restore']=guarded(restore)
 finally:
  if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
  report['finished_utc']=ns['now']();save();print('INDEPENDENT-FINISHED',flush=True)
