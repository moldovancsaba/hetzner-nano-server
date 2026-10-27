import base64,datetime,json,pathlib,statistics,subprocess,time
from fixtures import call,trim,unload,cases
ROOT=pathlib.Path(__file__).parent
VISION=['gemma4:e2b-it-qat','ministral-3:3b','granite3.2-vision:2b','qwen3-vl:2b','hf.co/ggml-org/SmolVLM-500M-Instruct-GGUF:Q8_0','moondream:1.8b']
TEXT=['granite3.3:2b','granite4:350m','granite4:1b-h','hf.co/QuantFactory/EuroLLM-1.7B-Instruct-GGUF:Q4_K_M','qwen3:1.7b']
report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hardware':'Hetzner CAX11, 2 ARM64 CPU, 4 GB RAM','container_cap_mib':2800,'context':2048,'vision':[],'text':[],'notes':['Separate image analytics and text/chat evaluations; no requirement for one combined model.','Model load failure is not a quality score.','Fixed 2048 context and 2800 MiB container cap maintained.','Repeated examples are not independent accuracy samples.','Previous round supplies cached public Atlas and OSM facts; no new external database queries.']}
def save(): (ROOT/'results.json').write_text(json.dumps(report,indent=2))
def metrics(r):return trim(r)
def countdata(text,key,n):
 try:d=json.loads(text);return isinstance(d,dict) and type(d.get(key)) is int and d[key]==n
 except Exception:return False
def parse_check(text,fn):
 try:d=json.loads(text);return bool(fn(d))
 except Exception:return False
def isdict(d):return isinstance(d,dict)
images={n:base64.b64encode((ROOT/n).read_bytes()).decode() for n in ['cats.png','poster.png']}
viscases=[
 ('photo_animals','cats.png','Return JSON only with exactly animal and count. Identify the main animal species in singular lowercase English and count how many are visible.',lambda t:parse_check(t,lambda d:isdict(d) and d.get('animal')=='cat' and type(d.get('count')) is int and d['count']==2),True),
 ('photo_count_plain','cats.png','How many cats are visible? Answer with the number only.',lambda t:t.strip().strip('.') in ['2','two','Two'],False),
 ('photo_remotes','cats.png','How many television remote controls are visible? Return JSON with remote_count as an integer.',lambda t:countdata(t,'remote_count',2),True),
 ('poster_ocr','poster.png','Read the printed text. Return JSON with venue (uppercase name), room (integer), opening_time (HH:MM).',lambda t:parse_check(t,lambda d:isdict(d) and d.get('venue')=='PANDORA' and type(d.get('room')) is int and d['room']==12 and d.get('opening_time')=='09:00'),True),
 ('poster_shapes','poster.png','There are colored geometric shapes below the text. Return JSON with exactly red_shape, blue_shape, green_shape. Values must be lowercase shape names.',lambda t:parse_check(t,lambda d:d=={'red_shape':'circle','blue_shape':'square','green_shape':'triangle'}),True),
 ('poster_missing_address','poster.png','Extract the street address if explicitly visible. Return JSON with street_address. If there is no street address, its value must be null. A room number is not a street address.',lambda t:parse_check(t,lambda d:isdict(d) and 'street_address' in d and d['street_address'] is None),True)]
extra=[
 ('chat_followup',[{'role':'user','content':'My project is called ClassScout. We help families find activities.'},{'role':'assistant','content':'Understood.'},{'role':'user','content':'What is my project called? Return JSON with project.'}],lambda d:d=={'project':'ClassScout'}),
 ('hungarian_extraction',[{'role':'user','content':'Budapesten élek, két gyermekem van, és úszást keresek nekik. Return JSON only with city, children (integer), activity (English lowercase). Use Budapest for the city and swimming for the activity.'}],lambda d:d=={'city':'Budapest','children':2,'activity':'swimming'}),
 ('chat_unknown_secret',[{'role':'user','content':'What is my MongoDB Atlas password? You have not been given it. Return JSON with known (boolean) and password (string or null). Do not invent a password.'}],lambda d:d=={'known':False,'password':None})]
previous='qwen3:1.7b'
try:
 for model in VISION:
  print('VISION START '+model,flush=True)
  unload(previous);previous=model
  show=call('/api/show',{'model':model});entry={'model':model,'show_ok':show['ok'],'capabilities':show.get('data',{}).get('capabilities',[]),'tests':[]};report['vision'].append(entry)
  if not show['ok']:entry['status']='not_imported';entry['error']=show.get('error');save();continue
  payload={'model':model,'prompt':'Identify the animals. Return JSON with animal and count.','images':[images['cats.png']],'think':False,'format':'json','stream':False,'keep_alive':'30m','options':{'num_ctx':2048,'num_predict':64,'temperature':0}}
  first=call('/api/generate',payload,150);entry['first_image']={**metrics(first),'response':first.get('data',{}).get('response','')};save()
  if not first['ok']:
   entry['status']='image_load_or_inference_failed';save();print('VISION FAILED '+model+' '+str(first.get('error')),flush=True);unload(model);continue
  entry['status']='ran'
  for name,image,prompt,validate,jsonformat in viscases:
   for trial in range(2):
    payload={'model':model,'prompt':prompt,'images':[images[image]],'think':False,'stream':False,'options':{'num_ctx':2048,'num_predict':96,'temperature':0}}
    if jsonformat:payload['format']='json'
    r=call('/api/generate',payload,100);text=r.get('data',{}).get('response','');valid=None
    if jsonformat:
     try:json.loads(text);valid=True
     except Exception:valid=False
    entry['tests'].append({'name':name,'image':image,'trial':trial+1,**metrics(r),'response':text,'json_valid':valid,'passed':r['ok'] and validate(text)});save()
    if not r['ok'] and any(k in r.get('error','').lower() for k in ['memory','terminated','out of']):
     entry['status']='failed_during_suite';break
   if entry['status']=='failed_during_suite':break
  entry['summary']={'passed':sum(t['passed'] for t in entry['tests']),'total':len(entry['tests'])};save();print('VISION DONE '+model+' '+json.dumps(entry['summary']),flush=True)
 for model in TEXT:
  print('TEXT START '+model,flush=True);unload(previous);previous=model
  show=call('/api/show',{'model':model});entry={'model':model,'capabilities':show.get('data',{}).get('capabilities',[]),'tests':[]};report['text'].append(entry)
  first=call('/api/generate',{'model':model,'prompt':'Reply READY.','think':False,'stream':False,'keep_alive':'30m','options':{'num_ctx':2048,'num_predict':12,'temperature':0}},100);entry['load']={**metrics(first),'response':first.get('data',{}).get('response','')};save()
  if not first['ok']:entry['status']='load_failed';save();continue
  entry['status']='ran'
  allcases=[(n,[{'role':'user','content':prompt}],fn) for n,prompt,fn in cases]+extra
  for name,messages,validate in allcases:
   for trial in range(2):
    r=call('/api/chat',{'model':model,'messages':messages,'think':False,'format':'json','stream':False,'options':{'num_ctx':2048,'num_predict':180,'temperature':0}},100)
    text=r.get('data',{}).get('message',{}).get('content','');valid=False;passed=False
    try:d=json.loads(text);valid=True;passed=bool(validate(d))
    except Exception:pass
    entry['tests'].append({'name':name,'trial':trial+1,**metrics(r),'response':text,'json_valid':valid,'passed':r['ok'] and passed});save()
  tools=[{'type':'function','function':{'name':'search_listings','description':'Search public listings','parameters':{'type':'object','properties':{'borough':{'type':'string'},'activity':{'type':'string'}},'required':['borough','activity']}}}]
  r=call('/api/chat',{'model':model,'messages':[{'role':'user','content':'Use search_listings to find Swimming in Brooklyn.'}],'tools':tools,'think':False,'stream':False,'options':{'num_ctx':2048,'num_predict':100,'temperature':0}},100)
  tc=r.get('data',{}).get('message',{}).get('tool_calls',[])
  entry['tool_call']={**metrics(r),'calls':tc,'passed':any(t.get('function',{}).get('name')=='search_listings' and t['function'].get('arguments',{}).get('borough')=='Brooklyn' and t['function'].get('arguments',{}).get('activity')=='Swimming' for t in tc)}
  # Free-form samples are saved for human review; nonempty is not a correctness grade.
  for language,prompt in [('en','How can I build a habit of walking daily? Answer in two short sentences.'),('hu','Hogyan szokhatok rá a napi sétára? Válaszolj magyarul, két rövid mondatban.')]:
   r=call('/api/chat',{'model':model,'messages':[{'role':'user','content':prompt}],'think':False,'stream':False,'options':{'num_ctx':2048,'num_predict':140,'temperature':0}},100)
   entry.setdefault('chat_samples',[]).append({'language':language,**metrics(r),'response':r.get('data',{}).get('message',{}).get('content','')});save()
  entry['summary']={'passed':sum(t['passed'] for t in entry['tests']),'total':len(entry['tests']),'json_valid':sum(t['json_valid'] for t in entry['tests'])};save();print('TEXT DONE '+model+' '+json.dumps(entry['summary']),flush=True)
finally:
 unload(previous)
 r=call('/api/generate',{'model':'qwen3:1.7b','prompt':'Reply READY.','think':False,'stream':False,'keep_alive':'30m','options':{'num_predict':12,'num_ctx':2048}},120)
 report['restored_original']=metrics(r);report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();print('RESTORED ORIGINAL',flush=True)
