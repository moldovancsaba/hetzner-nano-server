"""Install a confirmed workspace credential and commission read-only SLG operations."""
import argparse,json,pathlib,re,subprocess,sys
# The remote script ends with workflows_setup.setup(True). That also writes enabled=true to every scheduled trigger in
# the routine list, not only the SLG routines, so a trigger paused by hand is switched back on.
REMOTE=r'''
import sys,json,re,pathlib,subprocess,sqlite3
sys.path.insert(0,'/opt/narimato-factory');import slg,workflows_setup as w
v=json.load(sys.stdin);brand=v['brand'];key=v['key']
assert re.fullmatch('[a-z][a-z0-9-]{1,48}',brand) and re.fullmatch(r'slg_[A-Za-z0-9_-]{30,100}',key),'Invalid workspace or credential shape'
client=slg.Client(brand,key);client.test=True;tools=client.discover();stages=client.execute('slg_list_pipeline_stages',{})
assert stages.get('brand')==brand and stages.get('stages'),'Authenticated SLG contract unavailable'
root=pathlib.Path('/opt/narimato-factory');path=root/'factory.json';config=json.loads(path.read_text());env=pathlib.Path('/etc/paperclip-slg.env');keys={}
if env.exists():
 text=env.read_text().strip();assert text.startswith('SLG_SCOPED_KEYS=')
 keys=json.loads(text.split('=',1)[1].strip().strip("'"))
keys[brand]=key;encoded=json.dumps(keys,separators=(',',':'));assert "'" not in encoded
with sqlite3.connect('file:/var/lib/narimato-factory/factory.sqlite3?mode=ro',uri=True) as db:assert not db.execute("SELECT 1 FROM runs WHERE status='running'").fetchone(),'Wait for current factory work to finish'
env.write_text("SLG_SCOPED_KEYS='"+encoded+"'\n");env.chmod(0o600)
sales=config.setdefault('sales',{});sales.setdefault('brands',[])
if brand not in sales['brands']:sales['brands'].append(brand)
sales['crm_writes_enabled']=False;sales['delivery_enabled']=False;path.write_text(json.dumps(config,indent=2)+'\n')
subprocess.run(['systemctl','restart','narimato-factory'],check=True)
state=w.setup(True);runs=[]
for r in state['routines']:
 if r['kind'] in {'sales_connection','sales_pipeline'}:
  result=w.api('/routines/'+r['id']+'/run',{'source':'api','idempotencyKey':'slg-commission-'+brand+'-'+r['id'],'variables':{'slg_brand':brand}})
  runs.append({'kind':r['kind'],'run_id':result.get('id')})
print(json.dumps({'brand':brand,'authenticated':True,'tools':len(tools),'read_only_workflows':True,'crm_writes':False,'sending':False,'commissioning_runs':runs}))
'''
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--brand',required=True);parser.add_argument('--key-file',type=pathlib.Path,required=True);args=parser.parse_args();key=args.key_file.read_text().strip()
 if not re.fullmatch(r'slg_[A-Za-z0-9_-]{30,100}',key):raise ValueError('Invalid scoped SLG key format')
 # Credentials travel only through the encrypted process stdin, never a shell argument.
 remote='/opt/narimato-paperclip/configure-slg-remote.py'
 ssh=['ssh','-o','BatchMode=yes','-i','/Users/chappie/.ssh/hetzner_ai','root@2.29.113.132']
 installed=subprocess.run(ssh+['umask 077; cat > '+remote],input=REMOTE,text=True,capture_output=True)
 if installed.returncode:raise RuntimeError('Cannot install workspace configuration helper')
 result=subprocess.run(ssh+['python3 '+remote],input=json.dumps({'brand':args.brand,'key':key}),text=True,capture_output=True)
 if result.returncode:raise RuntimeError('SLG setup refused or failed; check workspace, key scope and whether factory work is active')
 print(result.stdout.strip())
if __name__=='__main__':
 try:main()
 except Exception as error:print(json.dumps({'status':'failed','reason':str(error)}));sys.exit(1)
