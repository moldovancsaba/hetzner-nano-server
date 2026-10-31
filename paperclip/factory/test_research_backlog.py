"""research_backlog counts the active ClassScout research tasks across every page of the issue list, so the
discovery limit holds above the Paperclip API's default page of 500 rows."""
import unittest
import urllib.parse
from unittest.mock import Mock
import worker,search_workflow,test_operations

class ResearchBacklogTests(unittest.TestCase):
 def setUp(self):
  self.helper=test_operations.OperationalTests();self.helper.setUp()
  self.config={'company_id':'company','projects':{'project':'ClassScout'},'agents':{'research':{'role':'research'}}}
 def tearDown(self):self.helper.tearDown()
 def board(self,rows):
  paths=[]
  def call(path):
   paths.append(path);query=urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
   return rows[int(query['offset'][0]):int(query['offset'][0])+min(int(query['limit'][0]),1000)]
  board=Mock();board.call.side_effect=call;return board,paths
 def test_every_page_is_counted_and_each_request_keeps_the_project_and_status_filters(self):
  rows=[{'id':'t%d'%i,'status':'todo','title':'Research %d'%i,'assigneeAgentId':'research'} for i in range(1530)]
  board,paths=self.board(rows)
  self.assertEqual(search_workflow.research_backlog(board,self.config,worker.database),1530)
  self.assertGreaterEqual(len(paths),2)
  for path in paths:
   query=urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
   self.assertTrue(path.startswith('/companies/company/issues?'))
   self.assertEqual(query['projectId'],['project']);self.assertEqual(query['status'],['backlog,todo,in_progress,in_review'])
 def test_finished_and_factory_test_tasks_are_not_counted_on_any_page(self):
  rows=[{'id':'a%d'%i,'status':'todo','title':'Research','assigneeAgentId':'research'} for i in range(1000)]
  rows+=[{'id':'done','status':'done','title':'Research','assigneeAgentId':'research'},{'id':'test','status':'todo','title':'[Factory test] Research','assigneeAgentId':'research'},{'id':'late','status':'in_progress','title':'Research','assigneeAgentId':'research'}]
  board,_=self.board(rows)
  self.assertEqual(search_workflow.research_backlog(board,self.config,worker.database),1001)
if __name__=='__main__':unittest.main()
