"""Native deployment patches preserve all source outside the exact owned hooks."""
import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('deploy_factory',Path(__file__).parent/'ops/deploy_factory.py')
deployment=importlib.util.module_from_spec(spec);spec.loader.exec_module(deployment)


class DeploymentTests(unittest.TestCase):
    def test_patch_preserves_current_native_work_and_is_idempotent(self):
        for name in ['worker.py','autonomy.py']:
            source=(Path(__file__).parents[1]/'factory'/name).read_text()
            if name=='worker.py':hook="  import source_exchange\n  source_exchange.save_offer(db,json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {},issue,page,facts)\n"
            else:hook=" import source_exchange\n source_exchange.coordinate(database,config.get('source_exchange',{}),board,config)\n"
            baseline=source.replace(hook,'')
            updated=deployment.patch_hooks(name,baseline)
            self.assertEqual(updated,source)
            self.assertEqual(deployment.patch_hooks(name,updated),source)

    def test_ambiguous_or_unknown_insertion_boundary_refuses_release(self):
        for source in ['', 'import source_exchange\n', 'def example():return None\n']:
            with self.assertRaises(ValueError):deployment.patch_hooks('autonomy.py',source)
