"""Run on inference host: bound runner caches under an exclusive maintenance lease."""
import pathlib, json, subprocess, time, urllib.request
root=pathlib.Path('/opt/narimato-ai');compose=root/'compose.yaml';original=compose.read_text()
assert 'LLAMA_ARG_CACHE_RAM' not in original
candidate=original.replace('      OLLAMA_KEEP_ALIVE: "30m"','      OLLAMA_KEEP_ALIVE: "30m"\n      LLAMA_ARG_CACHE_RAM: "128"\n      LLAMA_ARG_CTX_CHECKPOINTS: "2"')
assert candidate!=original
backup=root/'compose.before-context-cache.yaml';assert not backup.exists();backup.write_text(original)
key=dict(l.split('=',1) for l in pathlib.Path('/etc/narimato-model-cleanup.env').read_text().splitlines() if '=' in l)['GATEWAY_MAINTENANCE_KEY'].strip().strip('"').strip("'")
def lease(action,value=None):
 request=urllib.request.Request('http://127.0.0.1:8090/internal/model-storage',data=json.dumps({'action':action,'lease':value}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
 with urllib.request.urlopen(request,timeout=10) as r:return json.load(r)
was_timer=subprocess.run(['systemctl','is-active','--quiet','narimato-model-cleanup.timer']).returncode==0
subprocess.run(['systemctl','stop','narimato-model-cleanup.timer'],check=True);held=None
try:
 for _ in range(90):
  try:held=lease('acquire')['lease'];break
  except Exception:time.sleep(2)
 if not held:raise RuntimeError('No exclusive lease; no changes')
 compose.write_text(candidate)
 subprocess.run(['docker','compose','config','--quiet'],cwd=root,check=True)
 subprocess.run(['docker','compose','up','-d'],cwd=root,check=True)
 print('Runner cache capped at 128 MiB; at most two context checkpoints. Original context remains 2048.')
except Exception:
 compose.write_text(original)
 subprocess.run(['docker','compose','up','-d'],cwd=root,check=True)
 raise
finally:
 if held:lease('release',held)
 if was_timer:subprocess.run(['systemctl','start','narimato-model-cleanup.timer'],check=True)
