"""Tests for research.collect.fetch: the host allowlist applies to the first URL and to every redirect target,
https is required at each hop, and the response size bound still holds. Uses a fake HTTPS handler, so no network."""
import email.message,io,unittest,urllib.request,urllib.response
from research.collect import AllowlistedRedirects,fetch


class FakeHTTPS(urllib.request.HTTPSHandler):
    """Answers from a table of url -> (status, location, body) and records every URL it was asked for."""

    def __init__(self, routes):
        super().__init__()
        self.routes = routes
        self.seen = []

    def https_open(self, req):
        self.seen.append(req.full_url)
        status, location, body = self.routes[req.full_url]
        headers = email.message.Message()
        if location:
            headers['Location'] = location
        response = urllib.response.addinfourl(io.BytesIO(body), headers, req.full_url, status)
        response.msg = 'Found' if status in {301, 302} else 'OK'
        return response


def opener(routes):
    handler = FakeHTTPS(routes)
    return urllib.request.build_opener(AllowlistedRedirects, handler), handler


class Tests(unittest.TestCase):
    def test_redirect_within_the_allowlist_is_followed(self):
        client, handler = opener({
            'https://api.github.com/repos/a/b/releases/latest': (301, 'https://api.github.com/repositories/1/releases/latest', b''),
            'https://api.github.com/repositories/1/releases/latest': (200, None, b'{"tag_name":"v1"}'),
        })
        self.assertEqual(fetch('https://api.github.com/repos/a/b/releases/latest', 1024, client), b'{"tag_name":"v1"}')
        self.assertEqual(len(handler.seen), 2)

    def test_redirect_to_a_host_outside_the_allowlist_is_refused_before_it_is_requested(self):
        client, handler = opener({
            'https://huggingface.co/api/models': (302, 'https://evil.example/api/models', b''),
            'https://evil.example/api/models': (200, None, b'[]'),
        })
        with self.assertRaisesRegex(ValueError, 'Redirect target host not allowlisted'):
            fetch('https://huggingface.co/api/models', 1024, client)
        self.assertEqual(handler.seen, ['https://huggingface.co/api/models'])

    def test_relative_redirect_stays_on_the_listed_host(self):
        client, _ = opener({
            'https://ollama.com/library': (302, '/library/', b''),
            'https://ollama.com/library/': (200, None, b'ok'),
        })
        self.assertEqual(fetch('https://ollama.com/library', 1024, client), b'ok')

    def test_redirect_that_downgrades_to_http_is_refused(self):
        client, handler = opener({'https://openrouter.ai/api/v1/models': (302, 'http://openrouter.ai/api/v1/models', b'')})
        with self.assertRaisesRegex(ValueError, 'Redirect target host not allowlisted'):
            fetch('https://openrouter.ai/api/v1/models', 1024, client)
        self.assertEqual(len(handler.seen), 1)

    def test_first_url_outside_the_allowlist_is_refused_without_a_request(self):
        client, handler = opener({})
        for url in ['https://evil.example/x', 'http://huggingface.co/api/models', 'https://huggingface.co.evil.example/x']:
            with self.assertRaisesRegex(ValueError, 'Source host not allowlisted'):
                fetch(url, 1024, client)
        self.assertEqual(handler.seen, [])

    def test_oversized_response_is_refused(self):
        client, _ = opener({'https://huggingface.co/api/models': (200, None, b'x' * 11)})
        with self.assertRaisesRegex(ValueError, 'exceeds metadata budget'):
            fetch('https://huggingface.co/api/models', 10, client)


if __name__ == '__main__':
    unittest.main()
