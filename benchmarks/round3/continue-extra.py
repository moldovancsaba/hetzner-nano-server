import json,pathlib,time,subprocess,sys
root=pathlib.Path(__file__).parent
while True:
 try:
  if json.loads((root/'results.json').read_text()).get('completed_utc'):break
 except (ValueError,OSError):pass
 time.sleep(3)
subprocess.run([sys.executable,str(root/'run-extra.py')],check=True)
