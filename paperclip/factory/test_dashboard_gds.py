"""GDS static routes preserve CSP, confinement and file-size bounds without business work."""
import io
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import worker


class DashboardRoutes(unittest.TestCase):
 def test_root_and_exchange_share_the_governed_shell(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SOURCE_EXCHANGE_DASHBOARD':tmp}):
   Path(tmp,'index.html').write_text('<main>GDS fixture</main>')
   for path in ['/factory','/factory/','/factory/exchange/']:
    handler=types.SimpleNamespace(path=path,wfile=io.BytesIO(),send_response=Mock(),send_header=Mock(),end_headers=Mock(),respond=Mock())
    worker.Handler.do_GET(handler)
    handler.send_response.assert_called_once_with(200)
    self.assertIn(b'GDS fixture',handler.wfile.getvalue())
    headers=dict(call.args for call in handler.send_header.call_args_list)
    self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
    self.assertNotIn("script-src 'unsafe-inline'",headers['Content-Security-Policy'])
    self.assertEqual(headers['Cache-Control'],'no-store')
 def test_traversal_and_oversized_assets_are_refused(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SOURCE_EXCHANGE_DASHBOARD':tmp}):
   handler=types.SimpleNamespace(path='/factory/exchange/%2e%2e/private',respond=Mock())
   worker.Handler.do_GET(handler);self.assertEqual(handler.respond.call_args.args[0],404)
   path=Path(tmp,'huge.js')
   with path.open('wb') as file:file.truncate(4000001)
   handler=types.SimpleNamespace(path='/factory/exchange/huge.js',respond=Mock())
   worker.Handler.do_GET(handler);self.assertEqual(handler.respond.call_args.args[0],503)


if __name__=='__main__':unittest.main()
