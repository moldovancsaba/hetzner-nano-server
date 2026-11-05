"""Native deployment patches preserve all source outside the exact owned hooks."""
import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('deploy_factory',Path(__file__).parent/'ops/deploy_factory.py')
deployment=importlib.util.module_from_spec(spec);spec.loader.exec_module(deployment)


class DeploymentTests(unittest.TestCase):
    def test_patch_preserves_current_native_work_and_is_idempotent(self):
        for name in ['worker.py','autonomy.py','search_workflow.py']:
            source=(Path(__file__).parents[1]/'factory'/name).read_text()
            if name=='worker.py':hook="  import source_exchange\n  source_exchange.save_offer(db,json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {},issue,page,facts)\n"
            elif name=='autonomy.py':hook=" import source_exchange\n source_exchange.coordinate(database,config.get('source_exchange',{}),board,config)\n"
            else:hook="   import source_exchange\n   source_exchange.save_verified_page(database,job,page)\n"
            baseline=source.replace(hook,'')
            updated=deployment.patch_hooks(name,baseline)
            self.assertEqual(updated,source)
            self.assertEqual(deployment.patch_hooks(name,updated),source)

    def test_ambiguous_or_unknown_insertion_boundary_refuses_release(self):
        for source in ['', 'import source_exchange\n', 'def example():return None\n']:
            with self.assertRaises(ValueError):deployment.patch_hooks('autonomy.py',source)


class ModuleReleaseTests(unittest.TestCase):
    def setUp(self):
        import tempfile,json,sqlite3,hashlib,base64
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.native=self.root/'opt/narimato-factory';self.native.mkdir(parents=True)
        self.config=self.native/'factory.json';self.config.write_text(json.dumps({'source_exchange':{'offers_enabled':True,'events_enabled':True,'gap_tasks_enabled':False},'unrelated':{'schedule':'preserved'}}))
        self.module=self.native/'source_exchange.py';self.module.write_text('prior_version=True\n')
        self.state=self.root/'var/lib/narimato-factory/factory.sqlite3';self.state.parent.mkdir(parents=True)
        with sqlite3.connect(self.state) as db:
            db.execute('CREATE TABLE runs(status TEXT)');db.execute('CREATE TABLE business_effects(id TEXT)');db.execute("INSERT INTO business_effects VALUES('original')")
        (self.root/'proc/123/task/123').mkdir(parents=True)
        self.payload={'apply':False,'module_only':True,'expected':{'source_exchange.py':hashlib.sha256(self.module.read_bytes()).hexdigest()},'module':base64.b64encode(b'new_version=True\n').decode(),'patcher':'def patch_hooks(name,source):raise AssertionError("module release must not patch caller hooks")'}

    def remote(self,fail=False):
        import contextlib,io,json,re,sqlite3,types
        from unittest.mock import patch
        source=re.sub(r"'(/(?:opt|etc|var|proc)/)",lambda m:"'"+str(self.root)+m[1],deployment.REMOTE)
        failures=[fail]
        def command(args,**kwargs):
            if failures[0] and args[1:]==['start','narimato-factory.service']:
                failures[0]=False
                with sqlite3.connect(self.state) as db:db.execute("INSERT INTO business_effects VALUES('newer')")
                raise RuntimeError('injected readiness failure')
            return types.SimpleNamespace(stdout=b'123' if '--property=MainPID' in args else b'active')
        output=io.StringIO()
        with patch('sys.stdin',io.StringIO(json.dumps(self.payload))),contextlib.redirect_stdout(output),patch('subprocess.run',side_effect=command),patch('urllib.request.urlopen',return_value=io.StringIO('{"status":"ok"}')):
            try:exec(compile(source,'isolated-native-module-release','exec'),{})
            except SystemExit as exc:
                if exc.code not in (0,None):raise
        return json.loads(output.getvalue())

    def test_preflight_and_active_module_release_preserve_all_settings(self):
        before=self.config.read_bytes();proof=self.remote();self.assertFalse(proof['apply']);self.assertEqual(self.module.read_text(),'prior_version=True\n')
        self.payload['apply']=True;result=self.remote();self.assertTrue(result['apply']);self.assertEqual(result['business_flags'],'preserved');self.assertEqual(self.config.read_bytes(),before);self.assertEqual(self.module.read_text(),'new_version=True\n')
        self.assertFalse((self.root/'etc/systemd/system/narimato-factory.service.d/40-source-exchange.conf').exists())

    def test_busy_handler_and_stale_source_refuse_without_replacing_module(self):
        self.payload['apply']=True;(self.root/'proc/123/task/124').mkdir()
        self.assertEqual(self.remote()['state'],'busy');self.assertEqual(self.module.read_text(),'prior_version=True\n')
        self.module.write_text('changed=True\n')
        with self.assertRaises(RuntimeError):self.remote()
        self.assertEqual(self.module.read_text(),'changed=True\n')

    def test_failed_module_start_restores_code_without_restoring_business_database(self):
        import sqlite3
        before=self.config.read_bytes();self.payload['apply']=True
        with self.assertRaises(RuntimeError):self.remote(fail=True)
        self.assertEqual(self.config.read_bytes(),before);self.assertEqual(self.module.read_text(),'prior_version=True\n')
        with sqlite3.connect(self.state) as db:self.assertEqual(db.execute('SELECT count(*) FROM business_effects').fetchone()[0],2)


class WriterHandoffPatchTests(unittest.TestCase):
    def test_three_writer_patches_preserve_current_code_and_are_idempotent(self):
        hook=' import source_exchange\n source_exchange.require_native_catalog_writer(config,issue)\n'
        for name in ['publishing.py','refresh.py','program_updates.py']:
            source=(Path(__file__).parents[1]/'factory'/name).read_text();baseline=source.replace(hook,'');updated=deployment.patch_writer_handoff(name,baseline)
            self.assertEqual(updated,source);self.assertEqual(deployment.patch_writer_handoff(name,updated),source)

    def test_unknown_duplicate_or_moved_writer_entry_refuses_patch(self):
        for source in ['def unrelated():pass\n','def run(config,issue):\n pass\ndef run(other):\n pass\n','def run(config,issue):\n source_exchange.require_native_catalog_writer(config,issue)\n']:
            with self.assertRaises(ValueError):deployment.patch_writer_handoff('publishing.py',source)
        with self.assertRaises(ValueError):deployment.patch_writer_handoff('unknown.py','def run(config,issue):\n pass\n')


class WriterHandoffReleaseTests(ModuleReleaseTests):
    def setUp(self):
        import hashlib,inspect
        super().setUp()
        self.payload['module_only']=False;self.payload['writer_handoff']=True
        self.payload['patcher']=inspect.getsource(deployment.patch_writer_handoff)
        for name in ['publishing.py','refresh.py','program_updates.py']:
            p=self.native/name;p.write_text('def run(issue,board,config,web,database):\n return "preserved-original"\n');self.payload['expected'][name]=hashlib.sha256(p.read_bytes()).hexdigest()

    def test_writer_hook_release_preserves_configuration_and_installs_only_exact_patches(self):
        before=self.config.read_bytes();self.payload['apply']=True;result=self.remote()
        self.assertTrue(result['apply']);self.assertEqual(result['business_flags'],'preserved');self.assertEqual(self.config.read_bytes(),before)
        for name in ['publishing.py','refresh.py','program_updates.py']:
            text=(self.native/name).read_text();self.assertIn('source_exchange.require_native_catalog_writer(config,issue)',text);self.assertIn('return "preserved-original"',text)

    def test_writer_release_failure_restores_all_callers_without_losing_new_business_rows(self):
        import sqlite3
        before={name:(self.native/name).read_bytes() for name in ['publishing.py','refresh.py','program_updates.py']};self.payload['apply']=True
        with self.assertRaises(RuntimeError):self.remote(fail=True)
        for name,raw in before.items():self.assertEqual((self.native/name).read_bytes(),raw)
        with sqlite3.connect(self.state) as db:self.assertEqual(db.execute('SELECT count(*) FROM business_effects').fetchone()[0],2)


class ApplicationWriterPatchTests(unittest.TestCase):
    def test_application_writer_hooks_preserve_every_other_byte(self):
        hooks={'engine_ops.py':" import destination_handoff\n destination_handoff.require_native_destination_writer(config,issue,'management',slug)\n",'padel.py':" import destination_handoff\n destination_handoff.require_native_destination_writer(config,issue,'management','padel-africa')\n",'slg.py':" import destination_handoff\n destination_handoff.require_native_destination_writer(config,issue,'salesleadgenerator',client.brand)\n"}
        for name,hook in hooks.items():
            source=(Path(__file__).parents[1]/'factory'/name).read_text();self.assertEqual(source.count(hook),1)
            updated=deployment.patch_writer_handoff(name,source.replace(hook,''));self.assertEqual(updated,source);self.assertEqual(deployment.patch_writer_handoff(name,updated),source)


class ApplicationWriterReleaseTests(WriterHandoffReleaseTests):
    def setUp(self):
        import base64,hashlib
        super().setUp();self.payload['application_writers']=True
        self.payload['destination_guard']=base64.b64encode(b'guard_version=True\n').decode()
        stubs={'engine_ops.py':'def write_once(issue,board,config,database,execution,client,slug,kind,body,proof):\n return "preserved-engine"\n','padel.py':'def run(issue,board,config,web,database,execution):\n return "preserved-padel"\n','slg.py':'def mutate(client,name,args,issue,board,config,database,execution):\n """CRM writes are never equated to sent email or a won sale."""\n return "preserved-slg"\n'}
        for name,source in stubs.items():
            p=self.native/name;p.write_text(source);self.payload['expected'][name]=hashlib.sha256(p.read_bytes()).hexdigest()

    def test_application_release_installs_guard_and_preserves_all_configuration(self):
        before=self.config.read_bytes();self.payload['apply']=True;result=self.remote();self.assertTrue(result['apply']);self.assertEqual(self.config.read_bytes(),before)
        for name in ['engine_ops.py','padel.py','slg.py']:self.assertIn('destination_handoff.require_native_destination_writer',(self.native/name).read_text())
        self.assertEqual((self.native/'destination_handoff.py').read_text(),'guard_version=True\n')

    def test_unknown_existing_guard_refuses_before_mutation(self):
        p=self.native/'destination_handoff.py';p.write_text('different_guard=True\n');self.payload['apply']=True
        with self.assertRaises(RuntimeError):self.remote()
        self.assertEqual(p.read_text(),'different_guard=True\n');self.assertNotIn('destination_handoff',(self.native/'padel.py').read_text())

    def test_failed_application_release_removes_new_guard_and_preserves_new_business_rows(self):
        import sqlite3
        before={name:(self.native/name).read_bytes() for name in ['engine_ops.py','padel.py','slg.py']};self.payload['apply']=True
        with self.assertRaises(RuntimeError):self.remote(fail=True)
        for name,body in before.items():self.assertEqual((self.native/name).read_bytes(),body)
        self.assertFalse((self.native/'destination_handoff.py').exists())
        with sqlite3.connect(self.state) as db:self.assertEqual(db.execute('SELECT count(*) FROM business_effects').fetchone()[0],2)
