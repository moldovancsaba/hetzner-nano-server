"""A resumed benchmark must consult live inventory after candidate cleanup."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

class InventoryResumeTests(unittest.TestCase):
    def run_prepare(self, live):
        tree = ast.parse(Path('benchmarks/round6/run.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare')
        pulls = []
        inventory = [{'name':'candidate','digest':'frozen'}] if live else []
        def run(*args, **kwargs):
            pulls.append(args)
            inventory.append({'name':'candidate','digest':'frozen'})
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            scope = {'initial': {'candidate'}, 'unload': lambda: None,
                     'get': lambda _: {'models': inventory},
                     'post': lambda *a: {}, 'shutil': SimpleNamespace(disk_usage=lambda _: SimpleNamespace(free=10*1024**3)),
                     'plan': {'settings': {'disk_staging_margin_bytes': 100}},
                     'ROOT': Path(directory), 'subprocess': SimpleNamespace(run=run, STDOUT=-2)}
            exec(compile(ast.Module(body=[fn], type_ignores=[]), '<prepare>', 'exec'), scope)
            tag, _ = scope['prepare']({'model':'candidate'})
        return pulls, tag
    def test_removed_initial_model_is_pulled_again(self):
        pulls, tag = self.run_prepare(False)
        self.assertEqual(len(pulls), 1)
        self.assertEqual(tag['digest'], 'frozen')
    def test_live_model_is_reused(self):
        pulls, _ = self.run_prepare(True)
        self.assertFalse(pulls)

if __name__ == '__main__': unittest.main()
