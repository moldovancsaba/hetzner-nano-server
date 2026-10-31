"""Tests for provision.py: a re-run keeps every setting it does not derive (remote_llm, switches, limits), writes defaults
only for a first install, and drops keys that no code reads. The Paperclip API is replaced by an in-memory fake."""
import contextlib,io,json,pathlib,tempfile,unittest
from unittest import mock
import provision
class FakeApi:
 """Answers the few Paperclip calls provision makes; projects and agents get ids derived from their names."""
 def __init__(self):self.calls=[]
 def __call__(self,path,data=None,method=None):
  method=method or ('POST' if data is not None else 'GET');self.calls.append((method,path,data))
  if method=='GET' and path.endswith(('/projects','/agents','/issues')):return []
  if method=='POST' and path.endswith('/projects'):return {'id':'project-'+data['name'],'name':data['name']}
  if method=='POST' and path.endswith('/agent-hires'):return {'agent':{'id':'agent-'+data['name']}}
  return {}
class ProvisionTests(unittest.TestCase):
 def run_provision(self,previous=None,brave=True):
  """Runs main() against a temporary factory directory; returns the factory.json it wrote."""
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=pathlib.Path(tmp.name)
  company=root/'company.json';company.write_text(json.dumps({'id':'company-1'}))
  brave_env=root/'brave.env'
  if brave:brave_env.write_text('BRAVE_API_KEY=x\n')
  if previous is not None:(root/'factory.json').write_text(json.dumps(previous))
  with mock.patch.object(provision,'ROOT',root),mock.patch.object(provision,'COMPANY_FILE',company),mock.patch.object(provision,'BRAVE_ENV',brave_env),mock.patch.object(provision,'api',FakeApi()),contextlib.redirect_stdout(io.StringIO()):provision.main()
  return json.loads((root/'factory.json').read_text())
 def test_first_install_writes_defaults_without_optional_lanes(self):
  config=self.run_provision()
  self.assertEqual(config['company_id'],'company-1');self.assertEqual(config['search_candidate_limit'],3);self.assertTrue(config['search_enabled']);self.assertTrue(config['publishing_enabled'])
  self.assertNotIn('remote_llm',config);self.assertEqual(set(config['projects'].values()),set(provision_brands()));self.assertEqual({a['role'] for a in config['agents'].values()},{'research','quality','support','publication','search'})
 def test_every_key_written_on_a_first_install_is_read_by_code(self):
  import test_factory_config
  self.assertEqual(test_factory_config.unread_keys(self.run_provision()),[])
 def test_rerun_keeps_remote_llm_and_every_operator_setting(self):
  previous={'company_id':'old','projects':{'stale':'ClassScout'},'agents':{'stale':{'name':'x','role':'research'}},'search_enabled':False,'search_candidate_limit':5,'publishing_enabled':False,'operational_workflows_enabled':False,'catalog_batch_size':1,'audit_page_limit':2,'reviewer_user_id':'someone','remote_llm':{'enabled':True,'model':'m','monthly_cost':10.0},'automatic_quality_gate':{'enabled':True,'daily_write_limit':20},'growth_mode':{'enabled':True},'padel_enabled':True,'reliability_enabled':True,'padel_discovery_enabled':True,'engine_clients':{'padel-africa':True},'program_updates_enabled':True,'sales':{'brands':['b'],'crm_writes_enabled':False},'future_setting':{'a':1}}
  config=self.run_provision(previous)
  for key in ['remote_llm','automatic_quality_gate','growth_mode','padel_enabled','reliability_enabled','padel_discovery_enabled','engine_clients','program_updates_enabled','sales','future_setting','search_candidate_limit','publishing_enabled','operational_workflows_enabled','catalog_batch_size','audit_page_limit','reviewer_user_id']:self.assertEqual(config[key],previous[key],key)
 def test_rerun_rederives_ids_maps_and_the_brave_switch(self):
  config=self.run_provision({'company_id':'old','projects':{'stale':'ClassScout'},'agents':{'stale':{'name':'x','role':'research'}},'search_enabled':True},brave=False)
  self.assertEqual(config['company_id'],'company-1');self.assertNotIn('stale',config['projects']);self.assertNotIn('stale',config['agents']);self.assertFalse(config['search_enabled'])
 def test_rerun_drops_keys_that_no_code_reads(self):
  config=self.run_provision({'pilot_brand':'ClassScout','outreach_enabled':False,'max_source_pages_per_task':2,'automatic_quality_gate':{'enabled':True,'policy':'v1','daily_write_limit':10},'growth_mode':{'enabled':True,'coverage':'c','campaign':'x','active_research_limit':10},'sales':{'brands':[],'crm_writes_enabled':False,'delivery_enabled':False}})
  for key in ['pilot_brand','outreach_enabled','max_source_pages_per_task']:self.assertNotIn(key,config)
  self.assertEqual(config['automatic_quality_gate'],{'enabled':True,'daily_write_limit':10});self.assertEqual(config['growth_mode'],{'enabled':True});self.assertEqual(config['sales'],{'brands':[],'crm_writes_enabled':False})
 def test_carry_over_does_not_alias_the_earlier_nested_values(self):
  previous={'remote_llm':{'enabled':True}};config=provision.carry_over({},previous);config['remote_llm']['enabled']=False;self.assertTrue(previous['remote_llm']['enabled'])
def provision_brands():
 return ['Sales Lead Generator','ClassScout','Sportolok','Management','Padel Africa','Factory Operations']
if __name__=='__main__':unittest.main()
