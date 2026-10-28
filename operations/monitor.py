"""Low-cost operational watchdog. It observes; it never restarts inference or captures payloads."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway.metrics import Metrics
from operations.alerts import advance
from operations.notifications import deliver_pending


def evaluate(snapshot):
    alerts = {}
    if not snapshot.get('gateway_reachable'):
        alerts['gateway_unreachable'] = {'severity':'critical','message':'The inference gateway cannot be reached.'}
    queue = snapshot.get('queue', {})
    if queue.get('status') == 'degraded':
        alerts['inference_circuit_open'] = {'severity':'critical','message':'Inference is blocked after an uncertain upstream failure. Inspect active native work before recovery.'}
    if queue.get('active_for_seconds', 0) > 300:
        alerts['inference_stuck'] = {'severity':'critical','message':'One inference job has been active for over five minutes.'}
    if queue.get('oldest_wait_seconds', 0) > 60:
        alerts['queue_delay'] = {'severity':'warning','message':'Queued work has waited over one minute.'}
    if queue.get('metrics_write_failures', 0):
        alerts['metrics_write_failed'] = {'severity':'critical','message':'Operational metrics could not be written. Check disk space and database permissions.'}
    for unit, healthy in snapshot.get('services', {}).items():
        if not healthy:
            alerts['service_'+unit] = {'severity':'critical','message':'A required server service is inactive: '+unit+'.'}
    disk = snapshot.get('disk_free_gib', 0)
    if disk < 4:
        alerts['disk_critical'] = {'severity':'critical','message':'Less than 4 GiB disk space remains. Defer model downloads; preserve protected weights.'}
    elif disk < 6:
        alerts['disk_low'] = {'severity':'warning','message':'Less than 6 GiB disk space remains. Review model storage and capacity.'}
    if snapshot.get('oom_killed'):
        alerts['runtime_oom'] = {'severity':'critical','message':'The inference container reports an out-of-memory termination.'}
    if not snapshot.get('metrics_readable'):
        alerts['metrics_unreadable'] = {'severity':'warning','message':'Operational usage metrics cannot be read.'}
    for group in snapshot.get('usage', {}).get('projects', []):
        if group['purpose'] != 'production' or group['project'] in {'operator','unknown'}:
            continue
        # Cancellations are client choices, not provider failures.
        failures = max(0, group['failed']-group['errors'].get('cancelled',0))
        total = group['completed']+failures
        if failures >= 3 and total >= 5 and failures/total >= .2:
            alerts['failures_'+group['project']] = {'severity':'warning','message':'Repeated inference failures for '+group['project']+' in the last 15 minutes.'}
        if group['completed'] >= 5 and (group['timings']['duration_ms']['p95_ms'] or 0)>60000:
            alerts['latency_'+group['project']] = {'severity':'warning','message':'The last 15 minutes of '+group['project']+' work have a p95 completion time above 60 seconds.'}
        if group['errors'].get('unauthorized',0)>=3:
            alerts['auth_'+group['project']] = {'severity':'warning','message':'Repeated API authorization failures for '+group['project']+'.'}
        # Storage maintenance rejections are expected and excluded from this failure rule.
        unavailable = sum(group['errors'].get(code,0) for code in ['upstream_unavailable','usage_tracking_unavailable','upstream_state_unknown'])
        if unavailable >= 3:
            alerts['availability_'+group['project']] = {'severity':'critical','message':'Repeated API availability errors for '+group['project']+'.'}
    return alerts



def snapshot():
    result = {'gateway_reachable':False,'metrics_readable':False,
              'disk_free_gib':round(shutil.disk_usage('/').free/1024**3,3),'services':{}}
    for name in ['caddy','docker','narimato-gateway','narimato-chat']:
        result['services'][name] = subprocess.run(['systemctl','is-active','--quiet',name],timeout=5).returncode==0
    try:
        keys=json.loads(Path('/opt/narimato-ai/api-keys.json').read_text())
        req=urllib.request.Request('http://127.0.0.1:8090/v1/queue',headers={'Authorization':'Bearer '+keys['classscout'],'X-Request-Purpose':'test'})
        with urllib.request.urlopen(req,timeout=10) as response:result['queue']=json.load(response)
        result['gateway_reachable']=True
    except (OSError, ValueError):
        pass
    try:
        metrics=Metrics.readonly('/var/lib/narimato-gateway/metrics.sqlite3')
        try:result['usage']=metrics.summary(.25)
        finally:metrics.close()
        result['metrics_readable']=True
    except Exception:
        pass
    try:
        data=json.loads(subprocess.check_output(['docker','inspect','narimato-ollama'],text=True,timeout=10))[0]
        result['oom_killed']=data['State']['OOMKilled']
        result['services']['native_container']=data['State']['Running']
        result['runtime_id']=data['Id']
        try:
            pid=data['State']['Pid'];group=Path('/proc/'+str(pid)+'/cgroup').read_text().strip().split('::')[-1]
            events={k:int(v) for k,v in (line.split() for line in (Path('/sys/fs/cgroup'+group)/'memory.events').read_text().splitlines())}
            result['oom_kill_count']=events.get('oom_kill',0)
        except (OSError,ValueError,KeyError):
            result['oom_kill_count']=None
    except (OSError, ValueError, subprocess.SubprocessError):
        result['services']['native_container']=False
    return result


def track_oom(previous, data, now):
    """Docker's OOMKilled flag can stay true while the container is running.
    Track new cgroup events and retain a five-minute incident window instead.
    """
    old=previous.get('snapshot',{})
    historical=bool(data.get('oom_killed'))
    last=old.get('last_oom_at',previous.get('active_alerts',{}).get('runtime_oom',{}).get('first_seen_at',0))
    count=data.get('oom_kill_count');oldcount=old.get('oom_kill_count')
    if count is not None:
        if oldcount is not None and data.get('runtime_id')==old.get('runtime_id') and count>oldcount:
            last=now
        elif data.get('runtime_id')!=old.get('runtime_id') and count>0 and not last:
            last=now
    elif historical and not data.get('services',{}).get('native_container'):
        last=now
    elif historical and not last:
        last=now
    data['historical_oom_killed']=historical
    data['last_oom_at']=last
    data['oom_killed']=bool(last and now-last<300)
    return data


def check(path):
    path=Path(path);previous=json.loads(path.read_text()) if path.exists() else {}
    data=track_oom(previous,snapshot(),time.time());state=advance(previous,evaluate(data),time.time())
    state['snapshot']={key:value for key,value in data.items() if key!='usage'}
    deliver_pending(state, previous)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.chmod(0o600);tmp.replace(path)
    for change in state['changes']:
        if change['revision']>previous.get('revision',0):
            print(json.dumps(change),flush=True)
    return state


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true')
    parser.add_argument('--state',default='/var/lib/narimato-monitor/status.json');args=parser.parse_args()
    while True:
        check(args.state)
        if args.once:
            break
        time.sleep(30)
