"""Tests that scripts/deploy_gateway_update.py, retired because it ships only part of the gateway, refuses to run
without its explicit flag and does so before touching any path, key or service. The flag path is never run."""
import ast,subprocess,sys,unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/deploy_gateway_update.py'


class Tests(unittest.TestCase):
    def test_refuses_without_the_flag(self):
        result=subprocess.run([sys.executable,str(SCRIPT)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,1)
        self.assertIn('retired',result.stderr)
        self.assertNotIn('Traceback',result.stderr)

    def test_guard_comes_before_any_other_statement(self):
        # The flag path is never executed here: on the inference host it would run the real maintenance window.
        body=ast.parse(SCRIPT.read_text()).body
        self.assertIsInstance(body[0].value,ast.Constant)
        self.assertIsInstance(body[1],ast.Import)
        self.assertIsInstance(body[2],ast.If)
        self.assertIn('sys.exit',ast.unparse(body[2]))

    def test_docstring_says_retired(self):
        self.assertTrue(SCRIPT.read_text().startswith('"""RETIRED.'))


if __name__=='__main__':
    unittest.main()
