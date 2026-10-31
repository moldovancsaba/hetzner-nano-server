"""Tests for the factory worker and its web fetcher (net): URL and DNS restrictions, redirect and compressed
size limits, HTML text extraction, quote-verified fact validation, source URL caps, draft upsert,
markdown image escaping and task lookup from the wake context."""
import gzip,io,json,pathlib,tempfile,unittest
from unittest.mock import patch,Mock
import net,worker

class Tests(unittest.TestCase):
 def test_url_constraints(self):
  for value in ['file:///etc/passwd','http://user:pass@example.org/','http://example.org:8080/','http://localhost/','https://example.org/?access_token=secret','https://example.org/a\r\nx:y']:
   with self.assertRaises(net.FetchError):net.canonical_url(value)
  self.assertEqual(net.canonical_url('https://EXAMPLE.org/a?utm_source=x&city=ny#fragment'),'https://example.org/a?city=ny')
 def test_dns_must_be_all_public(self):
  for values in [['127.0.0.1'],['10.0.0.1'],['169.254.169.254'],['93.184.216.34','192.168.1.2']]:
   rows=[(2,1,6,'',(value,443)) for value in values]
   with patch('net.socket.getaddrinfo',return_value=rows):
    with self.assertRaises(net.FetchError):net.public_addresses('example.org',443)
 def test_private_redirect_not_followed(self):
  conn=Mock();conn.getresponse.return_value.status=302;conn.getresponse.return_value.getheaders.return_value=[('Location','http://127.0.0.1:3100/api/companies')]
  with patch('net.PinnedHTTP',return_value=conn),patch('net.public_addresses',side_effect=[['93.184.216.34'],net.FetchError('private')]):
   with self.assertRaises(net.FetchError):net.PublicWeb().raw('https://example.org')
  self.assertEqual(conn.request.call_count,1)
 def test_compressed_response_is_bounded(self):
  response=Mock();response.status=200;response.getheaders.return_value=[('Content-Encoding','gzip')];response.read.return_value=gzip.compress(b'x'*(net.MAX_BODY+2))
  conn=Mock();conn.getresponse.return_value=response
  with patch('net.PinnedHTTP',return_value=conn),patch('net.public_addresses',return_value=['93.184.216.34']):
   with self.assertRaises(net.FetchError):net.PublicWeb().raw('https://example.org')
 def test_html_scripts_are_not_evidence(self):
  parser=net.PageParser();parser.feed('<title>Test provider</title><script>SECRET INSTRUCTION</script><p>225 Atlantic Avenue</p><style>hidden</style>')
  text,title=parser.result();self.assertEqual(title,'Test provider');self.assertIn('225 Atlantic Avenue',text);self.assertNotIn('SECRET',text);self.assertNotIn('hidden',text)
 def test_robots_disallow_blocks_source(self):
  web=net.PublicWeb()
  with patch.object(web,'raw',return_value={'status':200,'body':b'User-agent: *\nDisallow: /private'}):
   with self.assertRaises(net.FetchError):web.check_robots('https://example.org/private')
 def test_supported_values_require_real_quote_and_value(self):
  page={'text':'Provider phone is 212-912-2400. Price is not provided.'}
  items=[{'field':'phone','value':'212-912-2400','quote':'Provider phone is 212-912-2400.'},{'field':'price','value':'Free','quote':'Price is not provided.'}]
  accepted,rejected=worker.validate_facts(items,page);self.assertEqual([row['field'] for row in accepted],['phone']);self.assertEqual(len(rejected),1)
 def test_fabricated_quote_is_rejected(self):
  facts,rejected=worker.validate_facts([{'field':'address','value':'Imaginary Avenue','quote':'Address is Imaginary Avenue'}],{'text':'No address has been supplied.'})
  self.assertEqual(facts,[]);self.assertTrue(rejected)
 def test_unknowns_are_not_filled(self):
  facts,rejected=worker.validate_facts([{'field':'price','value':None,'quote':None}],{'text':'A class provider.'})
  self.assertEqual(facts,[]);self.assertEqual(rejected,[])
 def test_duplicate_fields_rejected(self):
  with self.assertRaises(ValueError):worker.validate_facts([{'field':'name','value':None,'quote':None}]*2,{'text':'A class provider.'})
 def test_source_pages_capped_and_tracking_removed(self):
  issue={'title':'Research provider','description':'https://example.org/a?utm_source=x and https://example.org/a'}
  self.assertEqual(worker.source_urls(issue),['https://example.org/a'])
  issue['description']=' '.join('https://example.org/'+str(i) for i in range(3))
  with self.assertRaises(ValueError):worker.source_urls(issue)
 def test_draft_upsert_preserves_source_references(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(worker,'STATE',pathlib.Path(directory)):
   worker.initialize();page={'url':'https://example.org/venue','title':'Provider','sha256':'a'*64,'fetched_at':1};facts=[{'field':'name','value':'Provider','quote':'Provider is the venue'}]
   a=worker.save_draft('ClassScout',{'id':'issue-a'},page,facts);b=worker.save_draft('ClassScout',{'id':'issue-b'},page,facts);self.assertEqual(a,b)
   with worker.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM entities').fetchone()[0],1);self.assertEqual(db.execute('SELECT count(*) FROM facts').fetchone()[0],1)
 def test_support_does_not_replace_listing_draft(self):
  page={'url':'https://example.org/provider','title':'Provider','text':'Phone 212-912-2400','sha256':'a'*64,'fetched_at':1}
  facts=[{'field':'phone','value':'212-912-2400','quote':'Phone 212-912-2400'}]
  with patch.object(worker.WEB,'page',return_value=page),patch.object(worker,'Model'),patch.object(worker,'extract',return_value=(facts,[],{'context':8192})),patch.object(worker,'save_draft') as save:
   result=worker.research({'id':'support','title':'Contact provider','description':'https://example.org/provider'},'ClassScout','support','run','test')
  save.assert_not_called();self.assertEqual(result['entities'],[]);self.assertIn('212-912-2400',result['markdown']);self.assertIn('Suggested support response',result['markdown'])
 def test_source_markdown_cannot_embed_remote_image(self):
  self.assertEqual(worker.safe('![tracking](https://example.org/pixel)'),r'\!\[tracking\](https://example.org/pixel)')
 def test_expected_bridge_stop_does_not_fail_response(self):
  handler=worker.Handler.__new__(worker.Handler);handler.send_response=Mock();handler.send_header=Mock();handler.end_headers=Mock(side_effect=BrokenPipeError());handler.wfile=Mock()
  handler.respond(200,{'status':'in_review'});handler.wfile.write.assert_not_called()
 def test_task_comes_from_wake_context_not_model(self):
  board=Mock();board.call.return_value={'id':'00000000-0000-4000-8000-000000000001'}
  worker.locate_task(board,{'contextSnapshot':{'payload':{'issueId':'00000000-0000-4000-8000-000000000001'}}},'agent','company')
  board.call.assert_called_once_with('/issues/00000000-0000-4000-8000-000000000001')

if __name__=='__main__':unittest.main()
