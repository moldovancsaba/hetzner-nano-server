import pathlib,json,time,subprocess,sys
root=pathlib.Path(__file__).parent
while True:
 try:
  if json.loads((root/'results.json').read_text()).get('completed_utc'):break
 except (OSError,ValueError):pass
 time.sleep(3)
for name in ['supplement-text.py','vision-retries.py','schema-vision.py']:
 print('PHASE '+name,flush=True)
 subprocess.run([sys.executable,str(root/name)],check=True)
print('ALL FOLLOW-UP PHASES COMPLETE',flush=True)
