import json,unittest
from unittest.mock import Mock,patch
import slg,worker,test_operations
ID='0123456789abcdef01234567'
class SalesTests(unittest.TestCase):
 def setUp(self):
  self.helper=test_operations.OperationalTests();self.helper.setUp();self.client=slg.Client('seyu','slg_test');self.issue={'id':'i','title':'CRM change','description':'Exact change','projectId':'sales'};self.config={'sales':{'brands':['seyu'],'crm_writes_enabled':True}}
 def tearDown(self):self.helper.tearDown()
 def reply(self,value):return {'content':[{'type':'text','text':json.dumps(value)}]}
 def test_explicit_workspace_required(self):
  with self.assertRaises(ValueError):slg.Client('')
 def test_cross_workspace_call_refused_before_transport(self):
  self.client.transport=Mock()
  with self.assertRaises(ValueError):self.client.execute('slg_search_leads',{'brand':'dvsc'})
  self.client.transport.assert_not_called()
 def test_public_discovery_requires_all_six_tools(self):
  self.client.transport=Mock(return_value={'tools':[{'name':x} for x in slg.TOOLS]});self.assertEqual(len(self.client.discover()),6)
  self.client.transport.return_value={'tools':[]}
  with self.assertRaises(ValueError):self.client.discover()
 def test_read_call_is_brand_bound_and_capped(self):
  self.client.transport=Mock(return_value=self.reply({'leads':[]}));self.client.execute('slg_search_leads',{'limit':100})
  args=self.client.transport.call_args.args[0]['params']['arguments'];self.assertEqual(args['brand'],'seyu');self.assertEqual(args['limit'],20)
 def test_read_path_cannot_mutate(self):
  self.client.transport=Mock()
  with self.assertRaises(ValueError):self.client.execute('slg_update_lead_stage',{'leadId':ID,'stage':'WON'})
  self.client.transport.assert_not_called()
 def test_capture_does_not_accept_server_invented_defaults(self):
  with self.assertRaisesRegex(ValueError,'name'):self.client.arguments('slg_capture_lead',{'url':'https://example.org','companyName':'Example'})
 def test_lost_stage_requires_reason(self):
  with self.assertRaises(ValueError):self.client.arguments('slg_update_lead_stage',{'leadId':ID,'stage':'LOST'})
 def test_tool_error_is_not_an_empty_success(self):
  self.client.transport=Mock(return_value={'isError':True,'content':[{'type':'text','text':'secret server diagnostics'}]})
  with self.assertRaisesRegex(ValueError,'refused'):self.client.execute('slg_get_lead',{'leadId':ID})
 def test_write_is_applied_only_after_readback_and_never_repeated(self):
  self.client.execute=Mock(side_effect=[{'ok':True,'brand':'seyu','leadId':ID,'stage':'QUALIFIED'},{'_id':ID,'kanbanColumn':'QUALIFIED'}])
  with patch('slg.publishing.ensure_execution'):
   for _ in range(2):r=slg.mutate(self.client,'slg_update_lead_stage',{'leadId':ID,'stage':'QUALIFIED'},self.issue,Mock(),self.config,worker.database,{})
  self.assertTrue(r['ok']);self.assertEqual(self.client.execute.call_count,2)
 def test_lost_write_response_is_not_replayed(self):
  self.client.execute=Mock(side_effect=TimeoutError())
  with patch('slg.publishing.ensure_execution'):
   for _ in range(2):
    with self.assertRaises(ValueError):slg.mutate(self.client,'slg_update_lead_stage',{'leadId':ID,'stage':'QUALIFIED'},self.issue,Mock(),self.config,worker.database,{})
  self.assertEqual(self.client.execute.call_count,1)
 def test_write_disabled_fails_before_transport(self):
  self.client.execute=Mock();self.config['sales']['crm_writes_enabled']=False
  with self.assertRaises(ValueError):slg.mutate(self.client,'slg_update_lead_stage',{'leadId':ID,'stage':'QUALIFIED'},self.issue,Mock(),self.config,worker.database,{})
  self.client.execute.assert_not_called()
 def test_workflows_refuse_an_unconfirmed_workspace(self):
  with self.assertRaises(ValueError):slg.run({'projectId':'s','description':'Factory workflow: sales_pipeline\nSLG workspace: seyu'},Mock(),{'projects':{'s':'Sales Lead Generator'},'sales':{'brands':[]}},Mock(),worker.database,{})
