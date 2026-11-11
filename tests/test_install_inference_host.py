import pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import install_inference_host as inst
class CommentOnlyTests(unittest.TestCase):
 def test_python_comment_and_docstring_edits_are_comment_only_but_code_is_not(self):
  self.assertTrue(inst.comment_only('py','x=1\n','# why\nx=1  # note\n'))
  self.assertTrue(inst.comment_only('py','def f():\n """a"""\n return 1\n','def f():\n """b"""\n return 1\n'))
  self.assertFalse(inst.comment_only('py','x=1\n','x=2\n'))
 def test_unparsable_python_is_never_called_comment_only(self):
  self.assertFalse(inst.comment_only('py','x=1\n','x=(\n'))
 def test_json_ignores_formatting_not_values(self):
  self.assertTrue(inst.comment_only('json','{"a":1,"b":2}','{\n "b":2,\n "a":1\n}'))
  self.assertFalse(inst.comment_only('json','{"a":1}','{"a":2}'))
 def test_caddy_and_compose_ignore_comment_lines_and_trailing_blanks(self):
  self.assertTrue(inst.comment_only('caddy','a {\n  b\n}\n','# top\na {\n  # inner\n  b  \n}\n\n'))
  self.assertFalse(inst.comment_only('text','mem_limit: 2800m','mem_limit: 3000m'))
class ClassifyTests(unittest.TestCase):
 def test_equal_missing_and_unrecorded_differences(self):
  self.assertEqual(inst.classify('py','a','a',None),'OK')
  self.assertEqual(inst.classify('py','a',None,None),'MISSING')
  self.assertEqual(inst.classify('py','a','b',None,'x=1\n','x=2\n'),'BLOCKED')
  self.assertEqual(inst.classify('py','a','b',None,'x=1\n','# c\nx=1\n'),'UPDATE')
 def test_a_host_file_unchanged_since_the_last_install_is_updated_even_with_code_changes(self):
  self.assertEqual(inst.classify('py','new','old','old','x=1\n','x=2\n'),'UPDATE')
 def test_a_hand_edited_host_file_is_blocked_unless_forced(self):
  self.assertEqual(inst.classify('py','new','edited','old','x=1\n','# c\nx=1\n'),'BLOCKED')
  self.assertEqual(inst.classify('py','new','edited','old','x=1\n','x=2\n',force=True),'UPDATE')
class ManagedTests(unittest.TestCase):
 def test_every_managed_repository_file_exists_and_no_host_path_repeats(self):
  items=inst.managed()
  self.assertEqual([r for r,_,_,_ in items if not (ROOT/r).is_file()],[])
  paths=[h for _,h,_,_ in items];self.assertEqual(len(paths),len(set(paths)))
 def test_the_services_that_run_from_the_repository_are_covered(self):
  paths={h for _,h,_,_ in inst.managed()}
  for needed in ('/opt/narimato-gateway/gateway/server.py','/opt/narimato-chat/server.py','/opt/narimato-gateway/operations/monitor.py','/opt/narimato-model-cleanup/cleaner.py','/opt/narimato-discovery/collect.py','/etc/systemd/system/narimato-model-cleanup.timer','/etc/caddy/Caddyfile'):self.assertIn(needed,paths)
if __name__=='__main__':unittest.main()
