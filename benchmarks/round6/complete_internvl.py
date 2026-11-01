"""Finish only missing InternVL cases, preserving the published original run."""
import copy, hashlib, json, pathlib, subprocess
ROOT = pathlib.Path(__file__).resolve().parent
source = (ROOT/'run.py').read_text().split('timer=subprocess.run', 1)[0]
ns = {'__file__': str(ROOT/'run.py'), '__name__': 'round6_completion'}
exec(compile(source, 'round6_helpers', 'exec'), ns)
out = ROOT/'internvl-completion.json'
original = json.loads((ROOT/'results.json').read_text())
model = next(m for m in original['models'] if 'InternVL3_5' in m['model'])
report = json.loads(out.read_text()) if out.exists() else {
    'version': 'round6-internvl-completion.v1', 'started_utc': ns['now'](),
    'original_sha256': hashlib.sha256((ROOT/'results.json').read_bytes()).hexdigest(),
    'reason': 'Owner requested continuation; fix stale inventory and resume incomplete runner stop. Preserve recorded cases.',
    'model': copy.deepcopy(model), 'runtime': ns['get']('/api/version'),
}
m = report['model']
def save():
    temp = out.with_suffix('.tmp')
    temp.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    temp.replace(out)
def work():
    before = ns['memory']()
    tag, meta = ns['prepare'](m)
    assert tag['digest'] == model['tag']['digest'], 'Changed artifact; cannot mix outputs'
    report['verified_digest'] = tag['digest']
    m.update(meta); m['status'] = 'running'; save()
    fields = [('tests', ns['manifest']['recognition'], 'image_recognition'),
              ('robustness', ns['manifest']['robustness'], 'image_recognition'),
              ('counts', [c for c in ns['manifest']['recognition'] if c.get('count_probe')], 'count'),
              ('moderation', ns['moderation']['cases'], 'image_moderation'),
              ('moderation_robustness', ns['moderation'].get('robustness', []), 'image_moderation')]
    for field, cases, task in fields:
        m.setdefault(field, [])
        done = {r['id'] for r in m[field]}
        if len(done) == len(cases):
            m[field+'_status'] = 'completed'; continue
        for case in cases:
            if case['id'] in done: continue
            row = ns['image_case'](m['model'], case, task)
            m[field].append(row); save()
            print(field, case['id'], row['status'], row['seconds'], flush=True)
            if row['oom_kill_delta']: raise RuntimeError('OOM safety stop')
            if len(m[field]) >= 3 and all(r['status']=='failed' for r in m[field][-3:]):
                m[field+'_status'] = 'stopped_contract_failure'; break
        else: m[field+'_status'] = 'completed'
    m['oom_kill_delta'] = ns['memory']()['events'].get('oom_kill', 0)-before['events'].get('oom_kill', 0)
    m['status'] = 'completed' if all(m.get(f+'_status')=='completed' for f,_,_ in fields) else 'completed_with_module_failures'
# One renewable lease covers staging, inference and cleanup: no cleaner/client race.
# Lease acquisition waits for an empty queue; gateway safely rejects admission meanwhile.
def bounded_run():
    timer = subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode == 0
    initial = {t['name'].lower() for t in ns['get']('/api/tags')['models']}
    report['cleanup_timer_was_active'] = timer; save()
    subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'], check=True)
    try:
        work()
    except Exception as exc:
        m.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:800]); save()
    finally:
        try:
            ns['unload']()
            if m['model'].lower() not in initial:
                subprocess.run(['docker','exec','narimato-ollama','ollama','rm',m['model']],check=True,capture_output=True,timeout=60)
            m['temporary_weights_removed'] = not any(t['name'].lower()==m['model'].lower() for t in ns['get']('/api/tags')['models'])
            report['restore'] = ns['infer'](ns['payload']('granite4:1b-h','Reply READY.',options={'num_ctx':8192,'num_batch':128,'num_predict':12,'temperature':0,'prompt_cache_mib':128,'context_checkpoints':2}))
        finally:
            if timer: subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
            report['finished_utc'] = ns['now'](); save()
ns['guarded'](bounded_run)
print('FINISHED', m['status'], flush=True)
