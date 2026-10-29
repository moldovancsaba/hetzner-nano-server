import json,os,pathlib,tempfile,unittest,urllib.error
from unittest.mock import Mock,patch
import worker,segmind,search_budget as sb

PAGE={'url':'https://example.org/swim','title':'Example Swim','text':'Example Swim is at 12 Main Street.\nLessons cost $25 per class.\nOpen Monday to Friday 9am-5pm.'}
ON={'remote_llm':{'enabled':True}}
class Clock:
 def __init__(self):self.now=1800000000.
 def __call__(self):return self.now
def reply(facts,finish='STOP',cost='0.0123'):
 body=json.dumps({'candidates':[{'content':{'parts':[{'text':json.dumps({'facts':facts})}],'role':'model'},'finishReason':finish}],'usageMetadata':{'promptTokenCount':900,'candidatesTokenCount':80}}).encode()
 response=Mock();response.read.return_value=body;response.status=200;response.headers={'x-cost':cost} if cost is not None else {}
 response.__enter__ = lambda self:self;response.__exit__ = lambda self,*a:False
 return response
def http_error(code):return urllib.error.HTTPError('https://api.segmind.com/v1/x',code,'x',{},None)
def good():return [{'field':'price','value':'$25 per class','quote':'Lessons cost $25 per class.'},{'field':'opening_hours','value':'Monday to Friday 9am-5pm','quote':'Open Monday to Friday 9am-5pm.'},{'field':'phone','value':'','quote':''}]

class SegmindTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.state=patch.object(worker,'STATE',pathlib.Path(self.tmp.name));self.state.start();worker.initialize()
  self.env=patch.dict(os.environ,{'SEGMIND_API_KEY':'test-key-not-real'});self.env.start()
  self.clock=Clock();self.ledger=segmind.Ledger(worker.database,self.clock);self.limits=segmind.settings(ON)
 def tearDown(self):self.env.stop();self.state.stop();self.tmp.cleanup()
 def model(self,*outcomes):
  opener=Mock();opener.open.side_effect=list(outcomes);return segmind.RemoteModel(self.limits,self.ledger,opener),opener
 def augment(self,model,accepted=None,role='research',config=ON):
  return segmind.augment(PAGE,accepted if accepted is not None else [],config,role,worker.database,'job',worker.FIELDS,worker.validate_facts,model)
 def test_disabled_by_default_and_without_flag(self):
  self.assertIsNone(segmind.settings({}));self.assertIsNone(segmind.settings({'remote_llm':{'enabled':False}}));self.assertIsNone(segmind.settings({'remote_llm':{'enabled':'yes'}}))
  model=Mock();facts,rejected,metric,note=self.augment(model,config={'remote_llm':{'enabled':False}});self.assertEqual((facts,metric,note),([],None,None));model.call.assert_not_called()
 def test_only_the_research_role_may_use_it(self):
  for role in ['support','quality','publication','search']:
   model=Mock();self.assertEqual(self.augment(model,role=role)[2:],(None,None));model.call.assert_not_called()
 def test_nothing_to_add_when_name_address_price_and_hours_are_known(self):
  model=Mock();known=[{'field':field,'value':'x','quote':'x'} for field in ['name','address','price','opening_hours']];self.assertEqual(self.augment(model,known)[0],known);model.call.assert_not_called()
 def test_a_missing_core_field_alone_triggers_escalation(self):
  known=[{'field':field,'value':'x','quote':'x'} for field in ['address','price','opening_hours']]
  model,opener=self.model(reply([{'field':'name','value':'Example Swim','quote':'Example Swim is at 12 Main Street.'}]));facts=self.augment(model,known)[0]
  self.assertEqual(opener.open.call_count,1);self.assertEqual([f['field'] for f in facts],['address','price','opening_hours','name'])
 def test_limits_cannot_exceed_hard_ceilings_or_use_bad_models(self):
  for bad in [{'daily_cost':1000},{'daily_calls':0},{'daily_calls':True},{'model':'../admin'},{'model':'a b'},{'effort':'max'}]:
   with self.assertRaises(ValueError):segmind.settings({'remote_llm':{'enabled':True,**bad}})
 def test_verified_facts_are_added_and_cost_is_recorded(self):
  model,opener=self.model(reply(good()));facts,rejected,metric,note=self.augment(model,[{'field':'name','value':'Example Swim','quote':'Example Swim is at 12 Main Street.'}])
  self.assertEqual([f['field'] for f in facts],['name','price','opening_hours']);self.assertEqual(rejected,[]);self.assertEqual(metric['cost'],0.0123);self.assertIn('verbatim source quote',note)
  request=opener.open.call_args[0][0];self.assertEqual(request.full_url,'https://api.segmind.com/v1/gemini-3.8-flash');self.assertEqual(request.get_header('X-api-key'),'test-key-not-real')
  self.assertEqual(self.ledger.status()['today'],{'calls':1,'cost':0.0123})
 def test_request_carries_only_the_public_page_and_no_key_in_body(self):
  model,opener=self.model(reply([]));self.augment(model);sent=opener.open.call_args[0][0].data.decode()
  self.assertIn('Lessons cost $25',sent);self.assertNotIn('test-key-not-real',sent);self.assertIn('untrusted',sent)
 def test_invented_value_is_rejected_by_the_quote_gate(self):
  fake=[{'field':'price','value':'$5','quote':'Lessons cost $5 per class.'},{'field':'opening_hours','value':'Daily 24 hours','quote':'Open Monday to Friday 9am-5pm.'}]
  model,_=self.model(reply(fake));facts,rejected,metric,note=self.augment(model);self.assertEqual(facts,[]);self.assertEqual(len(rejected),2);self.assertIsNotNone(metric)
 def test_remote_cannot_override_a_local_fact(self):
  local=[{'field':'price','value':'$20','quote':'Lessons cost $20.'}]
  model,_=self.model(reply(good()));facts,*_=self.augment(model,local)
  self.assertEqual([f['value'] for f in facts if f['field']=='price'],['$20']);self.assertIn('opening_hours',[f['field'] for f in facts])
 def test_malformed_and_incomplete_output_leave_the_local_result_but_stay_charged(self):
  for finish in ['MAX_TOKENS','SAFETY']:
   model,_=self.model(reply(good(),finish=finish));facts,rejected,metric,note=self.augment(model);self.assertEqual(facts,[]);self.assertIn('unavailable',note)
  self.assertEqual(self.ledger.status()['today']['calls'],2)
  bad=reply([]);bad.read.return_value=b'not json';model,_=self.model(bad);self.assertIn('unavailable',self.augment(model)[3])
 def test_missing_cost_header_is_counted_at_the_ceiling(self):
  model,_=self.model(reply(good(),cost=None));self.augment(model);self.assertEqual(self.ledger.status()['today']['cost'],0.1)
 def test_daily_call_cap_stops_spending(self):
  self.limits=segmind.settings({'remote_llm':{'enabled':True,'daily_calls':2}});outcomes=[reply([]),reply([]),reply([])];model,opener=self.model(*outcomes)
  for _ in range(3):note=self.augment(model)[3]
  self.assertEqual(opener.open.call_count,2);self.assertIn('Daily remote-model allowance',note)
  self.clock.now+=86400;self.augment(model);self.assertEqual(opener.open.call_count,3)
 def test_daily_cost_cap_uses_the_ceiling_before_the_call(self):
  self.limits=segmind.settings({'remote_llm':{'enabled':True,'daily_cost':0.15,'call_cost_ceiling':0.1}});model,opener=self.model(reply([],cost='0.09'),reply([]))
  self.augment(model);self.assertIn('Daily remote-model allowance',self.augment(model)[3]);self.assertEqual(opener.open.call_count,1)
 def test_restart_cannot_reset_the_allowance(self):
  self.limits=segmind.settings({'remote_llm':{'enabled':True,'daily_calls':1}});model,_=self.model(reply([]));self.augment(model)
  other=segmind.Ledger(worker.database,self.clock)
  with self.assertRaises(sb.BudgetWait):other.reserve(self.limits,'again','m',1)
 def test_insufficient_credits_pauses_for_a_day_without_retry(self):
  model,opener=self.model(http_error(406),reply([]));self.assertIn('unavailable',self.augment(model)[3]);self.assertIn('insufficient',self.ledger.status()['pause_reason'])
  self.assertIn('paused',self.augment(model)[3]);self.assertEqual(opener.open.call_count,1);self.assertEqual(self.ledger.status()['today']['cost'],0)
 def test_rejected_key_pauses_until_an_explicit_unblock(self):
  model,opener=self.model(http_error(401),reply([]));self.augment(model);self.clock.now+=30*86400;self.assertIn('paused',self.augment(model)[3]);self.assertEqual(opener.open.call_count,1)
  self.ledger.unblock();self.augment(model);self.assertEqual(opener.open.call_count,2)
 def test_rate_limit_and_server_errors_back_off(self):
  for code in [429,500,502]:
   self.ledger.unblock();model,opener=self.model(http_error(code),reply([]));self.augment(model);self.assertIsNotNone(self.ledger.status()['paused_until']);self.augment(model);self.assertEqual(opener.open.call_count,1)
 def test_unconfirmed_call_is_counted_at_the_ceiling_and_pauses(self):
  model,opener=self.model(TimeoutError());note=self.augment(model)[3];self.assertIn('unavailable',note);self.assertEqual(self.ledger.status()['today']['cost'],0.1);self.assertIsNotNone(self.ledger.status()['paused_until'])
 def test_missing_key_is_a_quiet_local_fallback(self):
  with patch.dict(os.environ,clear=True):facts,rejected,metric,note=segmind.augment(PAGE,[],ON,'research',worker.database,'job',worker.FIELDS,worker.validate_facts)
  self.assertEqual((facts,metric),([],None));self.assertIn('unavailable',note)
 def test_redirects_are_not_followed(self):
  from brave import NoRedirect
  self.assertIsNone(NoRedirect().redirect_request(Mock(),Mock(),302,'Found',{},'https://evil.example/'))
 def test_oversized_input_is_refused_before_any_spend(self):
  model,opener=self.model(reply([]));big=[{'role':'user','content':'x'*(self.limits['max_input_chars']+5000)}]
  with self.assertRaises(segmind.RemoteError):model.call(big,segmind.schema(worker.FIELDS),'job')
  opener.open.assert_not_called();self.assertEqual(self.ledger.status()['today']['calls'],0)
 def test_worker_research_adds_remote_facts_for_research_and_never_for_support(self):
  page=dict(PAGE,sha256='abc',fetched_at=1800000000.);local=Mock();local.call.return_value=({'facts':[{'field':'name','value':'Example Swim','quote':'Example Swim is at 12 Main Street.'}]},{'usage':{}})
  issue={'id':'issue','title':'Research','description':'https://example.org/swim'};config={'remote_llm':{'enabled':True}}
  for role,expected in [('research',True),('support',False)]:
   remote=Mock();remote.call.return_value=({'facts':good()},{'model':'segmind:test','remote':True,'cost':0.01})
   with patch.object(worker,'Model',return_value=local),patch.object(worker.WEB,'page',return_value=page),patch.object(segmind,'RemoteModel',return_value=remote):
    result=worker.research(issue,'ClassScout',role,'run-'+role,'test',config)
   self.assertEqual(remote.call.called,expected);self.assertEqual('Lessons cost $25 per class.' in result['markdown'],expected)
   self.assertEqual(any(m.get('remote') for m in result['metrics']),expected)

if __name__=='__main__':unittest.main()
