"""Publish only the generated public benchmark snapshot; preserve private Caddy routes."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
KEY=Path.home()/'.ssh/hetzner_ai'
HOST='root@2.31.100.246'
def run(args,**kw):return subprocess.run(args,check=True,**kw)
run([sys.executable,str(ROOT/'scripts/build_dashboard.py')])
run(['ssh','-i',str(KEY),'-o','BatchMode=yes',HOST,'install -d -m 755 /var/www/narimato-benchmarks'])
for name in ['index.html','results.json']:
 run(['scp','-q','-i',str(KEY),str(ROOT/'dashboard'/name),HOST+':/var/www/narimato-benchmarks/'+name+'.new'])
remote=r'''
import subprocess,time
from pathlib import Path
root=Path('/var/www/narimato-benchmarks')
for name in ['index.html','results.json']:
 p=root/(name+'.new');p.chmod(0o644);p.replace(root/name)
p=Path('/etc/caddy/Caddyfile');original=p.read_text()
route='''+'"""'+'''
    # Public aggregate benchmark snapshot; never proxy private API data here.
    redir /benchmarks /benchmarks/ 308
    handle_path /benchmarks/* {
        root * /var/www/narimato-benchmarks
        header Cache-Control "public, max-age=300"
        header X-Content-Type-Options "nosniff"
        file_server
    }
'''+'"""'+'''
if '/var/www/narimato-benchmarks' not in original:
 marker='chatbotapi.haho.ai {'
 assert original.count(marker)==1
 backup=Path('/opt/narimato-ai/dashboard-caddy-backup-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
 backup.write_text(original);backup.chmod(0o600)
 p.write_text(original.replace(marker,marker+route,1))
 try:
  subprocess.run(['caddy','validate','--config',str(p)],check=True,capture_output=True)
  subprocess.run(['systemctl','reload','caddy'],check=True,capture_output=True)
 except Exception:
  p.write_text(original)
  subprocess.run(['systemctl','reload','caddy'],capture_output=True)
  raise RuntimeError('Dashboard route validation/reload failed; previous configuration restored') from None
print('Public benchmark snapshot published; existing private routes preserved.')
'''
run(['ssh','-i',str(KEY),'-o','BatchMode=yes',HOST,'python3 -'],input=remote,text=True)
