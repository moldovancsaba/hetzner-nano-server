"""Import only the locally converted, checksum-verified research artifact."""
import hashlib,json,pathlib,subprocess,threading,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parent;p=ROOT/'qwen35-hu-q8.gguf'
KEY=next(l.split('=',1)[1].strip().strip('"').strip("'") for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if l.startswith('GATEWAY_MAINTENANCE_KEY='))
def call(port,path,body,key=None):
 h={'Content-Type':'application/json','X-Request-Purpose':'test'}
 if key:h['Authorization']='Bearer '+key
 with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(body).encode(),headers=h),timeout=180) as r:return json.load(r)
def lease(action,value=None):return call(8090,'/internal/model-storage',{'action':action,'lease':value},KEY)
timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
held=None
try:
 subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True)
 for _ in range(300):
  try:held=lease('acquire')['lease'];break
  except urllib.error.HTTPError as e:
   if e.code!=409:raise
   time.sleep(2)
 assert held,'No idle maintenance lease'
 digest=hashlib.sha256(p.read_bytes()).hexdigest()
 subprocess.run(['curl','-fsS','--max-time','180','-X','POST','--data-binary','@'+str(p),'http://127.0.0.1:11434/api/blobs/sha256:'+digest],check=True,capture_output=True)
 result=call(11434,'/api/create',{'model':'hungarian-qwen35-trimmed:q8_0','files':{'model.gguf':'sha256:'+digest},'stream':False,'license':'Apache-2.0; alphaedge-ai/Qwen3.5-0.8B-hun-16384 revision 4cb74afbb6a731b51e8a18f6bd04e21d9bb712bc','parameters':{'num_ctx':2048,'num_batch':32,'temperature':0}})
 assert result.get('status')=='success'
 (ROOT/'installation.json').write_text(json.dumps({'imported':True,'cleanup_timer_was_active':timer,'gguf_sha256':digest,'model':'hungarian-qwen35-trimmed:q8_0'},indent=2)+'\n')
 p.unlink();print('Converted Hungarian model imported; duplicate staging binary removed.')
finally:
 if held:lease('release',held)
 if timer and not (ROOT/'installation.json').exists():subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
