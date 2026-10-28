"""Bounded native Hungarian chat adapter, independent of English context extensions."""
import copy,json,secrets,time

def request(data,profile):
 body={'model':data['model'],'messages':copy.deepcopy(data['messages']),'stream':False,'keep_alive':'1m','options':{'num_ctx':profile['num_ctx'],'num_batch':profile['num_batch'],'num_predict':data['max_tokens'],'temperature':data['temperature']}}
 if 'think' in profile:body['think']=profile['think']
 fmt=data.get('response_format')
 if fmt:
  if fmt.get('type')=='json_object':body['format']='json'
  elif fmt.get('type')=='json_schema':
   schema=fmt.get('json_schema',{}).get('schema')
   if not isinstance(schema,dict):raise ValueError('Provide a JSON schema object')
   body['format']=schema
  else:raise ValueError('Unsupported Hungarian response format')
 return body

def completion(response):
 if not response.get('done') or not isinstance(response.get('message'),dict):raise ValueError('Incomplete Hungarian response')
 message=copy.deepcopy(response['message']);message.pop('thinking',None)
 if message.get('tool_calls'):raise ValueError('Hungarian tool calls are not supported')
 if not isinstance(message.get('content'),str):raise ValueError('Invalid Hungarian response')
 prompt=response.get('prompt_eval_count',0);generated=response.get('eval_count',0)
 return {'id':'chatcmpl-'+secrets.token_hex(12),'object':'chat.completion','created':int(time.time()),'model':response['model'],'choices':[{'index':0,'message':message,'finish_reason':'length' if response.get('done_reason')=='length' else 'stop'}],'usage':{'prompt_tokens':prompt,'completion_tokens':generated,'total_tokens':prompt+generated}}
