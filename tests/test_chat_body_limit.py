"""Tests that the chat server's own request-size limit equals the one Caddy applies to /chat. chat/server.py starts
a server and needs production environment variables at import, so it is read as source, not imported."""
import ast,re,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
UNITS={'b':1,'kb':1000,'mb':1000**2,'gb':1000**3,'kib':1024,'mib':1024**2,'gib':1024**3}


def caddy_bytes(text):
    """Caddy reads sizes with go-humanize: KB, MB are powers of 1000; KiB, MiB are powers of 1024."""
    number,unit=re.fullmatch(r'(\d+)\s*([A-Za-z]*)',text).groups()
    return int(number)*UNITS[(unit or 'b').lower()]


def caddy_limit(path_matcher):
    text=(ROOT/'config'/'Caddyfile.example').read_text()
    found=re.search(r'handle '+re.escape(path_matcher)+r'\s*\{\s*request_body\s*\{\s*max_size\s+(\S+)',text)
    return caddy_bytes(found.group(1))


def chat_max_body():
    for node in ast.parse((ROOT/'chat'/'server.py').read_text()).body:
        if isinstance(node,ast.Assign) and any(getattr(t,'id',None)=='MAX_BODY' for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError('chat/server.py has no MAX_BODY')


class ChatBodyLimitTests(unittest.TestCase):
    def test_caddy_units_are_decimal_for_kb_and_binary_for_kib(self):
        self.assertEqual(caddy_bytes('128KB'),128000);self.assertEqual(caddy_bytes('256KiB'),262144);self.assertEqual(caddy_bytes('6MB'),6000000)

    def test_chat_server_limit_equals_the_caddy_limit_for_chat(self):
        self.assertEqual(chat_max_body(),caddy_limit('@chat'))

    def test_the_server_check_uses_the_constant(self):
        source=(ROOT/'chat'/'server.py').read_text()
        self.assertIn('0<n<=MAX_BODY',source);self.assertNotIn('256*1024',source)


if __name__=='__main__':unittest.main()
