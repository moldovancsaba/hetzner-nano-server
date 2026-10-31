"""Temporary round 3 helper, not a recurring automation: waits until results-extra.json has a completed_utc value, then runs reasoning-check.py."""
import pathlib,json,time,subprocess,sys
root=pathlib.Path(__file__).parent
while True:
 try:
  if json.loads((root/'results-extra.json').read_text()).get('completed_utc'):break
 except (ValueError,OSError):pass
 time.sleep(3)
subprocess.run([sys.executable,str(root/'reasoning-check.py')],check=True)
