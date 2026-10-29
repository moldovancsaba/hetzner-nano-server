"""Prepare review packets for the existing ClassScout ingest contract. No catalog writes."""
import argparse,datetime,hashlib,json,re,urllib.parse
from pathlib import Path
TARGETS={'The Art Farm NYC':'prov-tinyout-the-art-farm-nyc','Brooklyn Music Factory':'prov-tinyout-brooklyn-music-factory','West Side YMCA':'prov-west-side-ymca-summer-camp-2026'}
def host(url):return (urllib.parse.urlsplit(url).hostname or '').lower().removeprefix('www.')
def same_contact(field,a,b):
 if field=='phone':
  clean=lambda s:re.sub(r'\D','',s).removeprefix('1')
  return clean(a)==clean(b)
 return a.strip().casefold()==b.strip().casefold()
def plan(batch,catalog):
 catalog={r['id']:r for r in catalog};packets=[]
 for p in batch['providers']:
  draft=p.get('draft') or {};facts=draft.get('facts',[]);review=p.get('quality_review') or {};target=catalog.get(TARGETS.get(p['name']));issues=[];ops=[];notes=[]
  if p.get('research_status')!='in_review' or p.get('quality_status')!='in_review' or review.get('status')!='ready_for_human_review':issues.append('Research and quality review must pass before intake.')
  if target and host(target.get('website',''))!=host(p['url']):issues.append('Existing target official host differs; manual identity review required.')
  patch={};evidence=[]
  if target:
   notes.append('Existing catalog listing found; do not create a duplicate.')
   if p['name']=='West Side YMCA':issues.append('Existing listing is a summer-camp program. General branch contact/hours must not replace camp-specific facts.')
   if target.get('claimStatus') in ['claimed','claim_pending']:issues.append('Owner-managed record requires its existing owner edit/review workflow.')
   for f in facts:
    if f['field'] not in ['phone','email']:continue
    field=f['field'];previous=target.get(field) or ''
    if previous and same_contact(field,previous,f['value']):notes.append(field+' already agrees with source; no write needed.')
    elif previous:issues.append('Existing '+field+' differs; resolve scope/conflict before replacing it.')
    else:patch[field]=f['value'];evidence.append(f)
   if patch and not issues:ops=[{'resource':'provider','action':'patch','id':target['id'],'patch':patch}]
  else:
   issues.append('No matching listing was found in the bounded catalog lookup. Confirm location identity before creating a new provider.')
   issues.append('New listings need the canonical curatedProviderSchema, supported child age/program fields, public descriptions, image and publication checks; this extraction is not a complete provider document.')
  packet={'name':p['name'],'research_issue':p['research_identifier'],'quality_issue':p.get('quality_identifier'),'source_url':p['url'],'draft_id':p.get('draft_id'),'target_id':target['id'] if target else None,'status':'needs_enrichment_or_review' if issues else 'awaiting_owner_review' if ops else 'verified_no_contact_change','operations':ops,'facts':facts,'proposed_contact_evidence':evidence,'blockers':issues,'notes':notes,'excluded_mapping':['Facility opening hours are not recurringPrograms or class schedule.','Free-text price is not pricePerClass; missing price is never free.','Activities text is not an inferred category or age range.','Quoted source text is not a public description.']}
  packet['packet_sha256']=hashlib.sha256(json.dumps(packet,sort_keys=True,separators=(',',':')).encode()).hexdigest();packets.append(packet)
 return {'schema_version':1,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'batch_issue':batch['parent']['identifier'],'intake_endpoint':'https://classscout.ai/api/ingest','mode':'review_packets_only','catalog_mutations':0,'packets':packets}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--batch',required=True,type=Path);a.add_argument('--catalog',required=True,type=Path);a.add_argument('--output',required=True,type=Path);args=a.parse_args()
 result=plan(json.loads(args.batch.read_text()),json.loads(args.catalog.read_text()));args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'packets':len(result['packets']),'catalog_mutations':0,'statuses':{p['name']:p['status'] for p in result['packets']}}))
