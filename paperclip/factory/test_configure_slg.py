"""Tests for configure-slg.py: commissioning SLG routines must not change any other schedule trigger. A stateful fake of the
Paperclip routine API runs the real workflows_setup.setup, once the way the helper used to (setup(True)) and once through
the helper's guard."""
import copy,importlib.util,json,pathlib,re,tempfile,unittest
from unittest import mock
import workflows_setup
HERE=pathlib.Path(__file__).resolve().parent
module_path=HERE.parent/'configure-slg.py'
if not module_path.exists():module_path=pathlib.Path('/opt/narimato-paperclip/configure-slg.py')
spec=importlib.util.spec_from_file_location('paperclip_configure_slg',module_path);configure=importlib.util.module_from_spec(spec);spec.loader.exec_module(configure)
class FakePaperclip:
 """Routines and their triggers in memory; answers the calls workflows_setup.setup makes."""
 def __init__(self):self.routines={};self.count=0
 def next_id(self,prefix):self.count+=1;return prefix+str(self.count)
 def trigger(self,trigger_id):return next(t for r in self.routines.values() for t in r['triggers'] if t['id']==trigger_id)
 def __call__(self,path,body=None,method=None):
  method=method or ('POST' if body is not None else 'GET')
  if method=='GET' and path.endswith('/routines'):return copy.deepcopy(list(self.routines.values()))
  if method=='POST' and path.endswith('/routines'):
   routine={'id':self.next_id('r'),'latestRevisionId':'rev',**{k:body[k] for k in ['title','description','projectId','assigneeAgentId']},'triggers':[]};self.routines[routine['id']]=routine;return copy.deepcopy(routine)
  found=re.fullmatch(r'/routines/([^/]+)',path)
  if found and method=='GET':return copy.deepcopy(self.routines[found[1]])
  if found and method=='PATCH':routine=self.routines[found[1]];routine.update({k:v for k,v in body.items() if k!='baseRevisionId'});return copy.deepcopy(routine)
  found=re.fullmatch(r'/routines/([^/]+)/triggers',path)
  if found and method=='POST':trigger={'id':self.next_id('t'),**body};self.routines[found[1]]['triggers'].append(trigger);return {'trigger':copy.deepcopy(trigger)}
  found=re.fullmatch(r'/routine-triggers/([^/]+)',path)
  if found and method=='PATCH':trigger=self.trigger(found[1]);trigger.update(body);return copy.deepcopy(trigger)
  raise AssertionError('Unexpected call '+method+' '+path)
 def enabled(self):return {r['title']:[t['enabled'] for t in r['triggers']] for r in self.routines.values()}
class ConfigureSlgTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=pathlib.Path(tmp.name)
  config=json.loads((HERE/'factory.json').read_text());config['sales']={**config.get('sales',{}),'brands':['demo-brand']};(self.root/'factory.json').write_text(json.dumps(config))
  self.paperclip=FakePaperclip();patches=[mock.patch.object(workflows_setup,'ROOT',self.root),mock.patch.object(workflows_setup,'api',self.paperclip)]
  for patch in patches:patch.start();self.addCleanup(patch.stop)
  namespace={};exec(configure.GUARD,namespace);self.guarded=namespace['run_setup_preserving_triggers']
  workflows_setup.setup(True)
 def scheduled(self,title):
  routine=next(r for r in self.paperclip.routines.values() if r['title']==title);return routine['triggers'][0]
 def test_the_old_call_switched_a_paused_trigger_back_on(self):
  self.scheduled('Verify existing ClassScout listings')['enabled']=False
  workflows_setup.setup(True);self.assertTrue(self.scheduled('Verify existing ClassScout listings')['enabled'])
 def test_guard_leaves_a_hand_paused_trigger_paused_and_the_rest_enabled(self):
  self.scheduled('Verify existing ClassScout listings')['enabled']=False;before=self.paperclip.enabled()
  state=self.guarded(workflows_setup,self.root)
  self.assertEqual(self.paperclip.enabled(),before);self.assertFalse(self.scheduled('Verify existing ClassScout listings')['enabled']);self.assertTrue(self.scheduled('Discover Padel Africa sources')['enabled'])
  self.assertIs(workflows_setup.api,self.paperclip);self.assertTrue(json.loads((self.root/'workflows.json').read_text())['schedules_enabled']);self.assertIn('sales_pipeline',{r['kind'] for r in state['routines']})
 def test_guard_does_not_enable_schedules_that_are_off(self):
  workflows_setup.setup(False);self.assertFalse(any(v for values in self.paperclip.enabled().values() for v in values))
  self.guarded(workflows_setup,self.root);self.assertFalse(any(v for values in self.paperclip.enabled().values() for v in values))
 def test_guard_registers_the_sales_routines_once(self):
  self.guarded(workflows_setup,self.root);self.guarded(workflows_setup,self.root)
  titles=[r['title'] for r in self.paperclip.routines.values()]
  for title in ['Check SLG workspace connection','Review SLG partner pipeline','Prepare SLG partner briefing']:self.assertEqual(titles.count(title),1)
  self.assertTrue(all(not r['triggers'] for r in self.paperclip.routines.values() if r['title'].startswith(('Check SLG','Review SLG','Prepare SLG'))))
 def test_guard_gives_a_missing_trigger_the_current_schedule_mode(self):
  routine=next(r for r in self.paperclip.routines.values() if r['title']=='Check Padel Africa catalog');routine['triggers']=[]
  self.guarded(workflows_setup,self.root);self.assertTrue(self.scheduled('Check Padel Africa catalog')['enabled'])
 def test_guard_restores_the_api_even_when_setup_fails(self):
  with mock.patch.object(workflows_setup,'setup',side_effect=RuntimeError('boom')),self.assertRaises(RuntimeError):self.guarded(workflows_setup,self.root)
  self.assertIs(workflows_setup.api,self.paperclip)
 def test_remote_script_uses_the_guard_and_writes_no_unread_setting(self):
  compile(configure.REMOTE,'configure-slg-remote','exec')
  self.assertIn('run_setup_preserving_triggers(w,root)',configure.REMOTE);self.assertNotIn('setup(True)',configure.REMOTE);self.assertNotIn('delivery_enabled',configure.REMOTE)
if __name__=='__main__':unittest.main()
