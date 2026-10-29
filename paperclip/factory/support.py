"""Verified public-information support drafts; no customer delivery or account actions."""
import json,re,time,urllib.parse
import catalog,publishing

TOPICS={'phone':r'phone|telephone|call|contact','email':r'email|e-mail|contact','address':r'address|where|location|located|visit','website':r'website|web site|official site','price':r'price|cost|fee|tuition','opening_hours':r'opening|hours|open\b'}
UNSUPPORTED=r'\b(refund|payment|account|cancel|medical|legal|complaint|personal|order|reservation|capacity|spots|guarantee|availability|available|book|booking|schedule|timetable)\b'

def answer(question,row,page,facts):
 if re.search(UNSUPPORTED,question,re.I):return {'needs_human':True,'reply':'I can help with verified public provider information, but this question needs a person to check the relevant policy, current schedule, availability or account. I cannot confirm a booking, refund, payment or live class availability.','facts':[],'reason':'Requires policy, account, schedule or live availability confirmation'}
 requested=[k for k,p in TOPICS.items() if re.search(p,question,re.I)]
 if not requested:return {'needs_human':True,'reply':'I could not match this question to verified public contact, address, website, hours or price information. Please have a person review it.','facts':[],'reason':'Question is outside the supported public-information topics'}
 current={};supported=[];missing=[]
 for f in facts:
  if f.get('value') and f.get('quote') and publishing.norm(f['quote']) in publishing.norm(page['text']) and publishing.norm(f['value']) in publishing.norm(f['quote']):current.setdefault(f['field'],f)
 for key in requested:
  if key=='website':supported.append({'field':'website','value':page['url'],'quote':'Official page fetched directly'})
  elif key in current:supported.append(current[key])
  else:missing.append(key)
 pieces=[(f['field'].replace('_',' ').capitalize()+': '+f['value']) for f in supported]
 reply=row.get('name','The provider')+' — '+('; '.join(pieces) if pieces else 'I could not verify the requested information on the official page')+'.'
 if missing:reply+=' I could not confirm '+', '.join(k.replace('_',' ') for k in missing)+'; please check with the provider or have a person review it.'
 if 'opening_hours' in requested:reply+=' Facility opening hours do not confirm class times or availability.'
 if 'price' in requested:reply+=' This is the stated source wording; confirm which program and fee unit apply before relying on it.'
 return {'needs_human':bool(missing),'reply':reply,'facts':supported,'missing_fields':missing}

def run(issue,board,config,web,database,execution,client=None):
 client=client or catalog.Catalog();question=catalog.field(issue,'Question');id=None
 if not 4<=len(question)<=1200:raise ValueError('Add a public-information Question line between 4 and 1200 characters')
 try:
  id=catalog.resolve_provider(issue,database);row=client.get(id)
  if catalog.field(issue,'Provider name') and not catalog.field(issue,'Provider name').startswith('https://') and publishing.norm(row.get('name'))!=publishing.norm(catalog.field(issue,'Provider name')):raise ValueError('Listing name changed; confirm the current listing')
  from net import canonical_url
  url=canonical_url(row.get('website') or '');page=web.page(url)
  if urllib.parse.urlsplit(page['url']).hostname.removeprefix('www.')!=urllib.parse.urlsplit(url).hostname.removeprefix('www.'):raise ValueError('Official source identity requires review')
  facts,_=catalog.checked_facts(row,page)
  # Reuse source-supported research only for the same provider host and physical location.
  with database() as db:entities=db.execute("SELECT id,source_url FROM entities WHERE brand='ClassScout' AND status='ready_for_human_review' ORDER BY updated_at DESC LIMIT 30").fetchall()
  for entity in entities:
   if entity['source_url'].replace('://www.','://').rstrip('/')!=page['url'].replace('://www.','://').rstrip('/'):continue
   from refresh import address_key
   if address_key(row.get('address','')) not in address_key(page['text']) or not re.search(r'\d',row.get('address','')):continue
   with database() as db:extra=[dict(r) for r in db.execute('SELECT field,value,quote FROM facts WHERE entity_id=?',(entity['id'],))]
   # Current-page quotes are checked by answer(); other branches or stale quotes cannot enter a reply.
   facts+=extra
  response=cached_answer(database,id,question,page) or answer(question,row,page,facts);response.update(provider_id=id,source_url=page['url'],source_sha256=page['sha256'],checked_at=page['fetched_at'])
 except Exception as e:response={'needs_human':True,'reply':'I could not identify and verify the requested provider information. Please confirm the ClassScout listing and have a person check the source before replying.','provider_id':id,'reason':'Official source unavailable: '+type(e).__name__,'facts':[]}
 response['delivered_to_customer']=False;catalog.save_report(database,issue,'support_answer',response)
 from worker import safe
 lines=['## Support reply draft','','**Human review required. This reply has not been sent.**','',safe(response['reply']),'']
 if response.get('source_url'):lines+=['Official source: '+response['source_url'],'Checked: '+time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(response['checked_at']))+'.','']
 lines+=['Next action: '+('Confirm the missing information or policy with a person before replying.' if response['needs_human'] else 'Review the source and wording, then send through your normal support channel if appropriate.'),'No email, chat message, booking change, refund or customer account action was performed.']
 return {'stage':'support_escalation' if response['needs_human'] else 'support_draft','entities':[],'markdown':'\n'.join(lines),'report':response}


def cached_answer(database,id,question,page):
 topics={'what is the phone and email?':'contact','where is the address?':'address','what is the official website?':'website'}
 topic=topics.get(publishing.norm(question))
 if not topic:return None
 with database() as db:
  if not db.execute("SELECT 1 FROM sqlite_master WHERE name='support_knowledge'").fetchone():return None
  row=db.execute("SELECT * FROM support_knowledge WHERE provider_id=? AND topic=? AND status='ready' AND expires_at>?",(id,topic,time.time())).fetchone()
 if not row:return None
 value=json.loads(row['answer_json'])
 if value.get('source_url')!=page['url'] or value.get('source_sha256')!=page['sha256']:return None
 if not all(f['field']=='website' or (publishing.norm(f['value']) in publishing.norm(f['quote']) and publishing.norm(f['quote']) in publishing.norm(page['text'])) for f in value.get('facts',[])):return None
 return {**value,'reused_knowledge':True,'delivered_to_customer':False}
