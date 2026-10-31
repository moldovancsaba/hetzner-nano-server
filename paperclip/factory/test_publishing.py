"""Tests for publishing: mapping source pages to a listing (schedules, class price, location, same-host
sources, media checks) and run(), which publishes only with a valid human approval and an unchanged
packet and source, writes once, and does not retry a lost or partial write. The timetable and price
refusals are tested on formats, the parsers the production path uses."""
import copy,json,pathlib,tempfile,unittest
from unittest.mock import Mock,patch
import formats,worker,publishing as p

class PublishingTests(unittest.TestCase):
 def brief(self):return {'Publication name':'Keylab','Borough':'Brooklyn','Neighborhood':'Carroll Gardens','Activity':'Music','Format':'Classes','Draft reference':'a'*32,'urls':['https://example.org/classes']}
 def issue(self):return {'id':'issue','projectId':'project','title':'Prepare Keylab','description':'\n'.join(k+': '+v for k,v in self.brief().items() if k!='urls')+'\nhttps://example.org/classes'}
 def page(self):return {'url':'https://example.org/classes','title':'Keylab','text':'Keylab Music class at 94 Luquer St in Carroll Gardens, Brooklyn. Ages 9-12 - Fridays 3:30 pm, 60 minutes. Ages 13-17 - Fridays 4:30 pm, 75 minutes. Single class $42 per class.','sha256':'sourcehash','fetched_at':1}
 def test_complete_source_mapping_keeps_groups_and_price(self):
  n,proof=p.normalize_sources(self.brief(),[self.page()],[{'field':'address','value':'94 Luquer St','quote':'at 94 Luquer St'}]);self.assertEqual(n['neighborhoodRaw'],'Carroll Gardens');self.assertEqual(n['ageRangesRaw'],['9–12','Teens']);self.assertEqual(len(proof['schedules']),2);self.assertEqual(proof['price']['amount'],42)
 def test_facility_hours_cannot_become_class_timetable(self):
  with self.assertRaises(ValueError):formats.schedules('Opening hours Monday 9:00 am, 60 minutes. Classes for ages 9-12.')
 def test_session_fee_cannot_become_class_price(self):
  with self.assertRaises(ValueError):formats.price('Camp costs $175 per day and $500 per semester.')
 def test_multiple_class_prices_require_review(self):
  with self.assertRaises(ValueError):formats.price('$42 per class; $25 per class')
 def test_nav_location_cannot_override_editorial_location(self):
  brief=self.brief();brief['Neighborhood']='Imaginary Place'
  with self.assertRaises(ValueError):p.normalize_sources(brief,[self.page()],[])
 def test_off_host_sources_are_rejected(self):
  i=self.issue();i['description']+='\nhttps://other.example/classes'
  with self.assertRaises(ValueError):p.parse_brief(i)
 def test_collection_follows_only_relevant_same_provider_links(self):
  first={'url':'https://example.org/start','links':['https://other.example/classes','http://127.0.0.1/classes','/adult-classes','/kids-classes']};second={'url':'https://example.org/kids-classes','links':[]};web=Mock();web.page.side_effect=[first,second];brief={**self.brief(),'urls':[first['url']]}
  with patch('publishing.normalize_sources',side_effect=[ValueError('missing timetable'),({'title':'Ready'},{'sources':[]})]):pages,n,proof=p.collect_for_publication(brief,web,[])
  self.assertEqual([call.args[0] for call in web.page.call_args_list],[first['url'],second['url']]);self.assertEqual(len(pages),2)
 def test_collection_is_bounded_to_four_attempts(self):
  web=Mock();counter=[0]
  def page(url):
   counter[0]+=1;return {'url':url,'links':['/classes/page'+str(counter[0])]}
  web.page.side_effect=page;brief={**self.brief(),'urls':['https://example.org/start']}
  with patch('publishing.normalize_sources',side_effect=ValueError('missing ages')):
   with self.assertRaises(ValueError):p.collect_for_publication(brief,web,[])
  self.assertEqual(web.page.call_count,4)
 def test_redirected_source_cannot_change_provider_identity(self):
  web=Mock();web.page.return_value={'url':'https://other.example/classes','links':[]};brief={**self.brief(),'urls':['https://example.org/start']}
  with self.assertRaises(ValueError):p.collect_for_publication(brief,web,[])
 def test_sources_are_checked_before_sending_media(self):
  page=self.page();page['images']=['http://127.0.0.1/logo.png','https://private.example/photo.jpg']
  with patch('publishing.public_addresses',side_effect=ValueError('private')):self.assertEqual(p.media_candidates([page]),[])
 def scenario(self,approval=True):
  issue=self.issue();body={'draftId':'draft','entityKind':'provider','draftPayload':{'id':'prov-example','name':'Keylab'}};proof={'sources':[{'url':self.page()['url'],'sha256':self.page()['sha256']}]};packet_hash=p.sha({'body':body,'proof':proof})
  worker.initialize()
  with worker.database() as db:
   p.initialize(db);db.execute('INSERT INTO publication_packets VALUES(?,?,?,?,?,?,?,?,?,?,?)',(packet_hash,'issue',p.sha({'description':issue['description'],'title':issue['title'],'project':issue['projectId']}),'awaiting_approval',json.dumps(body),json.dumps(proof),'interaction',None,None,p.stamp(),p.stamp()))
  interaction={'id':'interaction','kind':'request_confirmation','companyId':'company','issueId':'issue','status':'accepted' if approval else 'pending','resolvedByUserId':'local-board','resolvedByAgentId':None,'effectiveResolverPolicy':'human_only','idempotencyKey':'publish-'+packet_hash,'result':{'outcome':'accepted'},'payload':{'detailsMarkdown':packet_hash}}
  board=Mock()
  def response(path):
   if path.endswith('/interactions'):return [interaction]
   if path.startswith('/heartbeat-runs/'):return {'status':'running','agentId':'pubagent','companyId':'company'}
   return {**issue,'companyId':'company','status':'in_progress','assigneeAgentId':'pubagent'}
  board.call.side_effect=response;web=Mock();web.page.return_value=self.page();client=Mock();client.existing_provider.return_value=None;client.call.return_value={'status':'published','privateVerification':{'verified':True,'verificationSource':'private-mongodb'},'publicVerification':{'verified':True,'verificationSource':'public-api'},'publishedEntityId':'prov-example'}
  return issue,board,web,client,interaction
 def test_pending_or_agent_approval_never_sends_publish(self):
  for mode in ['pending','agent']:
   with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
    i,b,w,c,a=self.scenario(approval=mode!='pending')
    if mode=='agent':a['resolvedByAgentId']='agent';a['resolvedByUserId']=None
    r=p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'});self.assertEqual(r['stage'],'awaiting_approval');c.call.assert_not_called()
 def test_human_approval_publishes_once_and_records_verified_receipt(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario();self.assertEqual(p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})['stage'],'published');self.assertEqual(p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})['stage'],'published');self.assertEqual(c.call.call_count,1)
 def test_source_change_invalidates_approval(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario();w.page.return_value={**self.page(),'sha256':'changed'}
   with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   c.call.assert_not_called()
 def test_payload_tampering_invalidates_approval(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario()
   with worker.database() as db:db.execute("UPDATE publication_packets SET body_json=?",(json.dumps({'tampered':True}),))
   with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   c.call.assert_not_called()
 def test_approval_is_bound_to_owner_issue_company_and_packet(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario()
   with worker.database() as db:packet=dict(db.execute('SELECT * FROM publication_packets').fetchone())
   for key,value in [('companyId','other'),('issueId','other'),('resolvedByUserId','other'),('effectiveResolverPolicy','anyone'),('idempotencyKey','old-packet')]:
    altered={**a,key:value};self.assertFalse(p.approval_valid(altered,packet,'company','local-board'))
 def test_expired_approval_cannot_publish(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario()
   with worker.database() as db:db.execute("UPDATE publication_packets SET created_at='2020-01-01T00:00:00+00:00'")
   with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   c.call.assert_not_called()
 def test_proof_tampering_cannot_publish(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario()
   with worker.database() as db:db.execute('UPDATE publication_packets SET proof_json=?',(json.dumps({'sources':[]}),))
   with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   c.call.assert_not_called()
 def test_existing_provider_is_never_overwritten(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario();c.existing_provider.return_value={'id':'prov-example'}
   with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   c.call.assert_not_called()
 def test_other_uncertain_packet_blocks_same_target(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario()
   with worker.database() as db:db.execute("INSERT INTO publication_packets SELECT 'other-hash','other-issue',input_hash,'uncertain',body_json,proof_json,NULL,NULL,NULL,created_at,updated_at FROM publication_packets LIMIT 1")
   with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   c.call.assert_not_called()
 def test_connector_cannot_use_ingest_for_writes(self):
  with self.assertRaises(ValueError):p.ClassScout().call('/api/ingest',{'operations':[{'resource':'provider','action':'delete','id':'x'}]})
 def test_identity_read_requires_definitive_not_found(self):
  client=p.ClassScout()
  with patch.object(client,'call',return_value={'results':[{'ok':False,'error':'provider not found'}]}):self.assertIsNone(client.existing_provider('x'))
  with patch.object(client,'call',return_value={'results':[]}):
   with self.assertRaises(ValueError):client.existing_provider('x')
 def test_skipped_public_check_cannot_be_claimed_as_verified(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario();c.call.return_value['publicVerification']['verificationSource']='public-api-skipped'
   self.assertEqual(p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})['stage'],'partial')
 def test_successful_identity_read_still_requires_matching_entity(self):
  client=p.ClassScout()
  with patch.object(client,'call',return_value={'results':[{'ok':True,'data':None}]}):
   with self.assertRaises(ValueError):client.existing_provider('x')
 def test_cancelled_task_cannot_publish_after_source_fetch(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario();original=b.call.side_effect
   b.call.side_effect=lambda path:{**original(path),'status':'cancelled'} if path=='/issues/issue' else original(path)
   with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   c.call.assert_not_called()
 def test_stopped_execution_cannot_publish(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario();original=b.call.side_effect
   b.call.side_effect=lambda path:{**original(path),'status':'cancelled'} if path.startswith('/heartbeat-runs/') else original(path)
   with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   c.call.assert_not_called()
 def test_invalid_clock_is_not_a_class_time(self):
  with self.assertRaises(ValueError):formats.schedules('Ages 9-12 - Fridays 25:99 pm, 60 minutes')
 def test_duplicate_class_rows_are_collapsed(self):
  line='Ages 9-12 - Fridays 3:30 pm, 60 minutes';self.assertEqual(len(formats.schedules(line+' '+line)),1)
 def test_lost_response_does_not_retry_write(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario();c.call.side_effect=TimeoutError()
   for attempt in range(2):
    with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   self.assertEqual(c.call.call_count,1)
 def test_partial_verification_is_not_success_and_is_not_republished(self):
  with tempfile.TemporaryDirectory() as d,patch.object(worker,'STATE',pathlib.Path(d)):
   i,b,w,c,a=self.scenario();c.call.return_value={'status':'partial','privateVerification':{'verified':True},'publicVerification':{'verified':False}}
   self.assertEqual(p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})['stage'],'partial')
   with self.assertRaises(ValueError):p.run(i,b,{'company_id':'company'},w,worker.database,c,execution={'agent_id':'pubagent','run_id':'run'})
   self.assertEqual(c.call.call_count,1)
if __name__=='__main__':unittest.main()
