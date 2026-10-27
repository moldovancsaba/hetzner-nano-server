import pathlib,json,base64,datetime
ROOT=pathlib.Path(__file__).parent
scope={'__file__':str(ROOT/'run.py')}
exec((ROOT/'run.py').read_text().split("previous='qwen3:1.7b'")[0],scope)
call,trim,unload=scope['call'],scope['trim'],scope['unload']
cases=scope['viscases']
specs={
 'photo_animals':{'animal':{'type':'string'},'count':{'type':'integer'}},
 'photo_remotes':{'remote_count':{'type':'integer'}},
 'poster_ocr':{'venue':{'type':'string'},'room':{'type':'integer'},'opening_time':{'type':'string'}},
 'poster_shapes':{'red_shape':{'type':'string'},'blue_shape':{'type':'string'},'green_shape':{'type':'string'}},
 'poster_missing_address':{'street_address':{'type':['string','null']}}}
models=[('hf.co/ggml-org/SmolVLM-500M-Instruct-GGUF:Q8_0',640,2048),('moondream:1.8b',640,2048)]
retry=json.loads((ROOT/'vision-retries.json').read_text())
for m in retry['models']:
 if m.get('status')=='ran':models.append((m['model'],m['max_image_dimension'],m['context']))
report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'JSON schema constrained outputs; expected answer values are NOT encoded in grammar','models':[]}
def save():(ROOT/'schema-vision.json').write_text(json.dumps(report,indent=2))
previous='qwen3:1.7b'
try:
 for model,size,ctx in models:
  print('SCHEMA START',model,flush=True);unload(previous);previous=model;entry={'model':model,'max_image_dimension':size,'context':ctx,'num_batch':32,'tests':[]};report['models'].append(entry)
  images={n:base64.b64encode((ROOT/(n if size==640 else n.replace('.png','-320.png'))).read_bytes()).decode() for n in ['cats.png','poster.png']}
  for name,image,prompt,validate,jsonformat in cases:
   if name not in specs:continue
   props=specs[name];schema={'type':'object','properties':props,'required':list(props),'additionalProperties':False}
   r=call('/api/generate',{'model':model,'prompt':prompt,'images':[images[image]],'think':False,'format':schema,'stream':False,'keep_alive':'30m','options':{'num_ctx':ctx,'num_batch':32,'num_predict':96,'temperature':0}},120)
   text=r.get('data',{}).get('response','');valid=False;shape=False
   try:
    d=json.loads(text);valid=True;shape=isinstance(d,dict) and set(d)==set(props)
   except Exception:pass
   entry['tests'].append({'name':name,**trim(r),'response':text,'json_valid':valid,'keys_match':shape,'passed':r['ok'] and validate(text)});save()
   if not r['ok']:entry['status']='failed_during_suite';break
  entry['summary']={'passed':sum(t['passed'] for t in entry['tests']),'total':len(entry['tests']),'json_valid':sum(t['json_valid'] for t in entry['tests'])};save();print('SCHEMA DONE',model,entry['summary'],flush=True)
finally:
 unload(previous);r=call('/api/generate',{'model':'qwen3:1.7b','prompt':'Reply READY.','think':False,'stream':False,'keep_alive':'30m','options':{'num_ctx':2048,'num_predict':12}},120);report['restored_original']=trim(r);save();print('SCHEMA RESTORED ORIGINAL',flush=True)
