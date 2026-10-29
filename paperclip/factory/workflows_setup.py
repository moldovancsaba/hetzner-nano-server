"""Owner-side idempotent configuration of native operating routines."""
import argparse,json,pathlib,urllib.request,urllib.error
ROOT=pathlib.Path('/opt/narimato-factory');BASE='http://127.0.0.1:3100/api'
def api(path,body=None,method=None):
 request=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'},method=method)
 try:return json.load(urllib.request.urlopen(request,timeout=30))
 except urllib.error.HTTPError as error:raise RuntimeError('Paperclip returned HTTP '+str(error.code)+': '+error.read(700).decode('utf-8','replace')) from None

def setup(activate=False,run_digest=False):
 config=json.loads((ROOT/'factory.json').read_text());company=config['company_id'];classscout=next(k for k,v in config['projects'].items() if v=='ClassScout');ops=next(k for k,v in config['projects'].items() if v=='Factory Operations');roles={v['role']:k for k,v in config['agents'].items()}
 specs=[('verify_catalog','Verify existing ClassScout listings','support',classscout,'0 8 * * *'),('publication_queue','Prepare complete ClassScout listings','publication',classscout,'45 8 * * *'),('audit_site','Audit ClassScout public pages','quality',classscout,'30 8 * * 1'),('operations_digest','Summarize ClassScout operations','support',ops,'0 9 * * *'),('support_answer','Draft a ClassScout reply','support',classscout,None)]
 if config.get('growth_mode',{}).get('enabled'):
  specs=[(kind,title,role,project,{'verify_catalog':'0 * * * *','publication_queue':'15,45 * * * *','audit_site':'30 8 * * *'}.get(kind,cron)) for kind,title,role,project,cron in specs]
  specs.append(('growth_dispatch','Run ClassScout discovery','search',classscout,'*/30 * * * *'))
 specs.append(('recover_evidence','Recover missing ClassScout evidence','support',classscout,'20 * * * *'))
 if config.get('padel_enabled'):
  padel_project=next(k for k,v in config['projects'].items() if v=='Padel Africa')
  specs.extend([('padel_maintenance','Check Padel Africa catalog','support',padel_project,'10 9 * * *'),('padel_intake','Submit a Padel Africa source','support',padel_project,None)])
 if config.get('reliability_enabled'):
  specs.append(('autonomous_coordination','Keep company workflows moving','support',ops,'*/5 * * * *'))
  specs.extend([('reliability_round','Recover stalled company work','support',ops,'25 * * * *'),('freshness_round','Check ClassScout content freshness','support',classscout,'35 */6 * * *'),('knowledge_round','Refresh ClassScout support knowledge','support',classscout,'50 */6 * * *')])
 if config.get('padel_discovery_enabled'):
  specs.append(('padel_discovery','Discover Padel Africa sources','search',next(k for k,v in config['projects'].items() if v=='Padel Africa'),'5 10,16 * * *'))
 if config.get('program_updates_enabled'):
  specs.append(('program_queue','Refresh ClassScout structured programs','support',classscout,'40 9 * * *'))
 if config.get('engine_clients',{}).get('padel-africa'):
  specs.append(('engine_maintenance','Maintain Padel Africa engine listings','support',next(k for k,v in config['projects'].items() if v=='Padel Africa'),'5 */6 * * *'))
 if config.get('engine_clients',{}).get('sportolok'):
  hu=next(k for k,v in config['projects'].items() if v=='Sportolok')
  specs.extend([('engine_maintenance','Maintain Sportolok engine listings','support',hu,'15 */6 * * *'),('engine_discovery','Discover Sportolok official sources','search',hu,'35 11,17 * * *')])
 if config.get('engine_clients'):
  specs.append(('management_overview','Check shared Management engine clients','support',next(k for k,v in config['projects'].items() if v=='Management'),'20 9 * * *'))
 if config.get('sales',{}).get('brands'):
  sales_project=next(k for k,v in config['projects'].items() if v=='Sales Lead Generator')
  specs.extend([('sales_connection','Check SLG workspace connection','support',sales_project,None),('sales_pipeline','Review SLG partner pipeline','support',sales_project,None),('sales_briefing','Prepare SLG partner briefing','support',sales_project,None)])
 existing=api('/companies/'+company+'/routines');existing=existing if isinstance(existing,list) else existing.get('routines',[]);routines=[];digest_run=None
 for kind,title,role,project,cron in specs:
  matches=[r for r in existing if r['title'].removeprefix('[Factory test] ')==title or (kind=='support_answer' and r['title']=='Draft a ClassScout reply for {{provider_name}}')]
  if len(matches)>1:raise ValueError('Duplicate routine titles need owner reconciliation: '+title)
  description='Factory workflow: '+kind+'\n\nUse the fixed, bounded ClassScout workflow. Eligible listings and content updates pass the configured automatic quality gate; ambiguous or unsupported changes are held. No customer messages. Known source pages are read directly; this routine does not request Brave searches.'
  if kind.startswith('sales_'):description='Factory workflow: '+kind+'\nSLG workspace: {{slg_brand}}'+('\nSLG lead ID: {{slg_lead_id}}' if kind=='sales_briefing' else '')+'\n\nUse the exact configured workspace only. Internal preparation; no CRM writes, outreach log entries, customer messages or stage advancement.'
  if kind=='program_queue':description='Factory workflow: program_queue\n\nQueue existing unclaimed same-branch program checks. Keep unmatched programs and manual owner work intact. Current source evidence and canonical validation remain mandatory.'
  if kind in {'engine_maintenance','engine_discovery','management_overview'}:description='Factory workflow: '+kind+'\n\nUse the authenticated vertical contract for this project. Keep literal source evidence and native hard/safety gates. Customer sending and Hungarian rewriting remain disabled.'
  if kind=='growth_dispatch':description='Factory workflow: growth_dispatch\n\nDispatch the next evidence-seeking ClassScout NYC campaign intent only when the shared Brave budget and production queue have capacity. Child search tasks use the existing cooldown, quota, evidence and automatic publication policies.'
  if kind=='padel_discovery':description='Factory workflow: padel_discovery\n\nQueue one official-source discovery intent in the next canonical Padel Africa city. Shared Brave reserve, cooldown and all tenant/receipt checks apply. No forced publication.'
  if kind=='autonomous_coordination':description='Factory workflow: autonomous_coordination\n\nDeliver up to ten due handoffs, plan at most two safe evidence continuations, and verify stopped executions. Preserve all packet/receipt and human review gates. No inference or Brave requests in the coordinator; downstream tasks retain their own guards. Never retry unchanged source evidence without a released parser change.'
  if kind=='reliability_round':description='Factory workflow: reliability_round\n\nClassify held work, surface exact evidence requirements, bounded retries and stopping rules. Saved evidence may resume through an independent continuation; uncertain writes are never replayed.'
  if kind=='freshness_round':description='Factory workflow: freshness_round\n\nRecheck up to three existing ClassScout providers against official source pages. Changed evidence feeds the independent research/quality/update pipeline. Claimed providers remain protected. Program price/schedule changes require a dedicated canonical contract.'
  if kind=='knowledge_round':description='Factory workflow: knowledge_round\n\nPrepare reusable source-grounded public-information answers for up to three exact branches; expire after 24h and invalidate failed rechecks. Record evidence gaps. No customer messages.'
  if kind=='padel_maintenance':description='Factory workflow: padel_maintenance\n\nVerify the authenticated Padel Africa tenant and Africa territory, then record its bounded machine catalog and engine lifecycle counts. No catalog writes or external messages.'
  if kind=='padel_intake':description='Factory workflow: padel_intake\nOfficial source URL: {{source_url}}\nProvider name: {{provider_name}}\nCity: {{city}}\nStreet address: {{address}}'
  if kind=='support_answer':description='Factory workflow: support_answer\nProvider name: {{provider_name}}\nQuestion: {{question}}'
  body={'title':title,'description':description,'projectId':project,'assigneeAgentId':roles[role],'status':'active','concurrencyPolicy':'skip_if_active','catchUpPolicy':'skip_missed','activityGatePolicy':'always'}
  if kind.startswith('sales_'):body.update(concurrencyPolicy='always_enqueue',variables=[{'name':'slg_brand','label':'SLG workspace slug','type':'text','required':True}]+([{'name':'slg_lead_id','label':'Exact SLG lead ID','type':'text','required':True}] if kind=='sales_briefing' else []))
  if kind=='support_answer':body.update(concurrencyPolicy='always_enqueue',variables=[{'name':'provider_name','label':'Provider name or listing link','type':'text','required':True},{'name':'question','label':'Question','type':'text','required':True}])
  if kind=='padel_intake':body.update(concurrencyPolicy='always_enqueue',variables=[{'name':name,'label':label,'type':'text','required':True} for name,label in [('source_url','Official source URL'),('provider_name','Provider name'),('city','City in Padel Africa coverage'),('address','Exact street address')]])
  if matches:
   saved=api('/routines/'+matches[0]['id'])
   allowed_assignees={roles[role]}
   if kind=='verify_catalog':allowed_assignees.add(roles['quality']) # Explicit controller migration; evidence review stays independent.
   if 'Factory workflow: '+kind not in (saved.get('description') or '') or saved.get('projectId')!=project or saved.get('assigneeAgentId') not in allowed_assignees:raise ValueError('Existing routine ownership or purpose does not match: '+title)
  else:saved=api('/companies/'+company+'/routines',body)
  if run_digest and kind=='operations_digest':digest_run=api('/routines/'+saved['id']+'/run',{'source':'api','idempotencyKey':'workflow-acceptance-20261028-operations_digest'})
  # Update after the canary issue snapshots its test title.
  saved=api('/routines/'+saved['id'],{**body,'baseRevisionId':saved['latestRevisionId']},'PATCH')
  if cron is None:
   routines.append({'kind':kind,'id':saved['id'],'title':title,'project_id':project,'manual_only':True,'enabled':True});continue
  detail=api('/routines/'+saved['id']);triggers=[t for t in detail.get('triggers',[]) if t['kind']=='schedule']
  if len(triggers)>1:raise ValueError('Multiple schedule triggers require reconciliation: '+title)
  trigger_body={'kind':'schedule','cronExpression':cron,'timezone':'Europe/Budapest','enabled':activate}
  if not triggers:trigger=api('/routines/'+saved['id']+'/triggers',trigger_body)['trigger']
  else:
   trigger=triggers[0]
   if trigger.get('cronExpression')!=cron or trigger.get('timezone')!='Europe/Budapest' or trigger.get('enabled')!=activate:
    trigger=api('/routine-triggers/'+trigger['id'],{'cronExpression':cron,'timezone':'Europe/Budapest','enabled':activate},'PATCH')
  routines.append({'kind':kind,'id':saved['id'],'title':title,'project_id':project,'trigger_id':trigger['id'],'cron':cron,'timezone':'Europe/Budapest','enabled':activate})
 state={'routines':routines,'timezone':'Europe/Budapest','schedules_enabled':activate,'support':'event-driven, draft-only','rollout_issue':'NAR-36','growth_mode':config.get('growth_mode',{}).get('enabled',False)};(ROOT/'workflows.json').write_text(json.dumps(state,indent=2)+'\n')
 return {'routines':routines,'digest_canary':{k:digest_run.get(k) for k in ['id','status','executionIssueId']} if digest_run else None}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--activate',action='store_true');parser.add_argument('--run-digest-canary',action='store_true');args=parser.parse_args();print(json.dumps(setup(args.activate,args.run_digest_canary),indent=2))
