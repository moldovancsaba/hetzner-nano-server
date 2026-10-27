#!/usr/bin/env python3
"""Explicit, language-specific diagnostic. Does not change models/routing or certify language support."""
import argparse,datetime,json,pathlib,sys,time,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser()
p.add_argument('--language',choices=['hu'],required=True)
p.add_argument('--model',required=True)
p.add_argument('--project',choices=['classscout','habigoal'],required=True)
a=p.parse_args()
key=json.loads((ROOT/'private/api-keys.json').read_text())[a.project]
cases=[
 {'id':'hu_number_extraction','messages':[{'role':'user','content':'Budapesten élek, két gyermekem van, és úszást keresek nekik. Return JSON with city, children (integer), activity (English lowercase).'}],'format':True},
 {'id':'hu_advice','messages':[{'role':'user','content':'Hogyan szokhatok rá a napi sétára? Válaszolj magyarul, két rövid mondatban.'}],'format':False}]
report={'language':a.language,'model':a.model,'project':a.project,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'diagnostic only; fluent human review and task-specific acceptance required','tests':[]}
for c in cases:
 payload={'model':a.model,'messages':c['messages'],'reasoning_effort':'none','temperature':0,'max_tokens':180}
 if c['format']:payload['response_format']={'type':'json_object'}
 req=urllib.request.Request('https://chatbotapi.haho.ai/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 start=time.monotonic();row={'id':c['id']}
 try:
  with urllib.request.urlopen(req,timeout=100) as res:d=json.load(res)
  row.update({'status':200,'response':d['choices'][0]['message']['content'],'usage':d.get('usage')})
 except urllib.error.HTTPError as e:row.update({'status':e.code,'error_type':'HTTPError'})
 except Exception as e:row.update({'status':0,'error_type':type(e).__name__})
 row['seconds']=round(time.monotonic()-start,4);report['tests'].append(row)
path=pathlib.Path(__file__).parent/(a.language+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print(path)
