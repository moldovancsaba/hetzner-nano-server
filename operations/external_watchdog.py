"""Independent host reachability check. An expected unauthorized reply needs no API credential."""
import argparse,json,pathlib,sys,time,urllib.error,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from operations.alerts import advance
from operations.notifications import deliver_pending

def reachable():
    request=urllib.request.Request('https://chatbotapi.haho.ai/v1/queue',headers={'X-Request-Purpose':'test','User-Agent':'Haho-External-Health/1.0'})
    try:
        urllib.request.urlopen(request,timeout=15).close()
        return False
    except urllib.error.HTTPError as error:
        if error.code!=401:return False
        try:return json.loads(error.read(1024)).get('error',{}).get('code')=='unauthorized'
        except (ValueError,AttributeError):return False
    except (OSError,urllib.error.URLError):return False

def check(path):
    path=pathlib.Path(path);previous=json.loads(path.read_text()) if path.exists() else {}
    ok=reachable()
    observed={} if ok else {'inference_host_unreachable':{'severity':'critical','message':'The inference HTTPS gateway is unreachable or is not returning its expected authenticated API response. Check host, network, TLS, proxy and gateway.'}}
    state=advance(previous,observed,time.time());state['reachable']=ok
    deliver_pending(state,previous)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.chmod(0o600);tmp.replace(path)
    for change in state['changes']:
        if change['revision']>previous.get('revision',0):print(json.dumps(change),flush=True)
    return state

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');parser.add_argument('--state',default='/var/lib/narimato-external-watchdog/status.json');args=parser.parse_args()
    while True:
        check(args.state)
        if args.once:break
        time.sleep(30)
