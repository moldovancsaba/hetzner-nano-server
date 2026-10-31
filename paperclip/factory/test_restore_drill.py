"""Tests for restore-drill.py: the report's network, production-file and image statements come from measurements. The helpers
that turn /proc network tables and file contents into those statements are checked here; the drill itself needs Docker."""
import importlib.util,pathlib,tempfile,unittest
HERE=pathlib.Path(__file__).resolve().parent
module_path=HERE.parent/'restore-drill.py'
if not module_path.exists():module_path=pathlib.Path('/opt/narimato-paperclip/restore-drill.py')
spec=importlib.util.spec_from_file_location('paperclip_restore_drill',module_path);drill=importlib.util.module_from_spec(spec);spec.loader.exec_module(drill)
DEV_HEADER='Inter-|   Receive                                                |  Transmit\n face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n'
LOOPBACK='    lo:       0       0    0    0    0     0          0         0        0       0    0    0    0     0       0          0\n'
UPLINK='  eth0:    1200      10    0    0    0     0          0         0      900       8    0    0    0     0       0          0\n'
ROUTE_HEADER='Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n'
DEFAULT_ROUTE='eth0\t00000000\t0102A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n'
class EgressTests(unittest.TestCase):
 def test_loopback_only_with_mode_none_has_no_way_out(self):
  result=drill.egress_paths(DEV_HEADER+LOOPBACK,ROUTE_HEADER,'none');self.assertEqual(result,{'network_mode':'none','interfaces':[],'routes':0,'egress':False})
 def test_any_other_interface_is_a_way_out(self):
  result=drill.egress_paths(DEV_HEADER+LOOPBACK+UPLINK,ROUTE_HEADER,'none');self.assertTrue(result['egress']);self.assertEqual(result['interfaces'],['eth0'])
 def test_a_route_through_another_interface_is_a_way_out(self):
  self.assertTrue(drill.egress_paths(DEV_HEADER+LOOPBACK,ROUTE_HEADER+DEFAULT_ROUTE,'none')['egress'])
 def test_a_network_mode_other_than_none_is_a_way_out_even_without_interfaces(self):
  self.assertTrue(drill.egress_paths(DEV_HEADER+LOOPBACK,ROUTE_HEADER,'bridge')['egress'])
class ProductionFileTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=pathlib.Path(tmp.name)
  self.a=self.root/'a.json';self.b=self.root/'b.env';self.a.write_text('{"x":1}');self.b.write_text('KEY=1\n');self.paths=[str(self.a),str(self.b),str(self.root/'missing')]
 def test_untouched_files_report_no_change(self):
  before=drill.fingerprint(self.paths);self.assertEqual(set(before),{str(self.a),str(self.b)});self.assertEqual(drill.changed_files(before,drill.fingerprint(self.paths)),[])
 def test_a_rewrite_with_the_same_bytes_is_not_a_change(self):
  before=drill.fingerprint(self.paths);self.a.write_text('{"x":1}');self.assertEqual(drill.changed_files(before,drill.fingerprint(self.paths)),[])
 def test_changed_removed_and_added_files_are_reported(self):
  before=drill.fingerprint(self.paths);self.a.write_text('{"x":2}');self.b.unlink();(self.root/'missing').write_text('new')
  self.assertEqual(drill.changed_files(before,drill.fingerprint(self.paths)),sorted([str(self.a),str(self.b),str(self.root/'missing')]))
 def test_fingerprints_do_not_keep_file_contents(self):
  self.assertNotIn('KEY=1',repr(drill.fingerprint(self.paths)))
 def test_watched_files_are_the_production_configuration(self):
  self.assertIn('/etc/paperclip-access.env',drill.WATCHED);self.assertNotIn('/var/lib/narimato-factory/factory.sqlite3',drill.WATCHED)
class ReportTests(unittest.TestCase):
 def test_report_statements_are_not_constants(self):
  source=module_path.read_text()
  for constant in ["'network_egress':False","'production_files_changed':False","proof['image_matches_production']=True"]:self.assertNotIn(constant,source)
if __name__=='__main__':unittest.main()
