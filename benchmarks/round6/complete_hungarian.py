"""Finish unattempted cases after an overly broad one-error stop; never rerun a failed case."""
import json,pathlib,threading,subprocess,time,shutil,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
source=(ROOT/'run.py').read_text().split("timer=subprocess.run",1)[0]
ns={'__file__':str(ROOT/'run.py'),'__name__':'round6_hu_completion'};exec(compile(source,'round6_shared','exec'),ns)
report=json.loads((ROOT/'results.json').read_text());ns['report']=report
report.setdefault('completion_events',[]).append({'at':ns['now'](),'reason':'Original runner stopped on one bounded token-repeat error. Execute only not-yet-attempted Hungarian cases under the frozen rule: stop on unsafe uncertainty/OOM or three consecutive technical failures. Preserve existing failed case and all previous outputs.'})
prior=report.pop('finished_utc',None);report.setdefault('prior_restorations',[]).append(report.pop('restore',None));save=ns['save'];guarded=ns['guarded'];unload=ns['unload'];memory=ns['memory'];now=ns['now'];plan=ns['plan'];cases=ns['hu']['cases'];initial=ns['initial']
ns['report']=report;ns['ns']['report']=report;ns['ns']['save']=save
resume_models=[m for m in report['models'] if m['task']=='text' and len(m.get('hungarian',[]))<35 and m.get('error')=='Hungarian runtime failure; stop candidate']
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 for m in resume_models:
  candidate=next(c for c in plan['candidates'] if c['model']==m['model']);model=m['model'];done={t['id'] for t in m['hungarian']};m.setdefault('prior_errors',[]).append({'error':m.pop('error',None),'error_type':m.pop('error_type',None)})
  try:
   tag,meta=guarded(lambda:ns['prepare'](candidate));assert tag['digest']==m['tag']['digest'],'Changed artifact; stop';before=memory();m['status']='running';save()
   for case in cases:
    if case['id'] in done:continue
    row=guarded(lambda c=case:ns['hu_case'](model,c));m['hungarian'].append(row);save();print('HU-REMAINDER',model,case['id'],row['ok'],flush=True)
    if memory()['events'].get('oom_kill',0)>before['events'].get('oom_kill',0):raise RuntimeError('OOM; stop')
    if not row['ok'] and row.get('error_type') in ['TimeoutError','URLError','OSError']:raise RuntimeError('Upstream uncertainty; stop')
    if len(m['hungarian'])>=3 and all(not t['ok'] for t in m['hungarian'][-3:]):raise RuntimeError('Three consecutive technical failures; stop')
   m['status']='completed_with_case_errors' if any(not t['ok'] for t in m['hungarian']) else 'completed';m['hungarian_all_cases_attempted']=len(m['hungarian'])==35
  except Exception as e:m.update(status='failed',error_type=type(e).__name__,error=str(e)[:800])
  finally:
   guarded(unload)
   if model.lower() not in initial:guarded(lambda:subprocess.run(['docker','exec','narimato-ollama','ollama','rm',model],check=True,capture_output=True,timeout=60));m['temporary_weights_removed']=True
   m['finished_utc']=now();save()
finally:
 try:
  def restore():
   unload();return ns['infer'](ns['payload']('granite4:1b-h','Reply READY.',options={'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}))
  report['restore']=guarded(restore)
 finally:
  if timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
  report['finished_utc']=now();save();print('COMPLETION-FINISHED',flush=True)
