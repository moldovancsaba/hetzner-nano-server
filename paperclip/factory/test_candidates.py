"""The oldest-touched-first rule: candidates are stamped when the system works on them and the one touched longest ago
is always next, so no candidate can hold a queue slot in a loop. Covers candidates.py and its two users, the
publication queue (pipeline.run_queue) and the evidence recheck queue (evidence.run_queue)."""
import unittest
from unittest.mock import Mock
import candidates,evidence,pipeline,worker
import test_operations

class CandidateTouchTests(unittest.TestCase):
 def setUp(self):self.helper=test_operations.OperationalTests();self.helper.setUp()
 def tearDown(self):self.helper.tearDown()
 def add(self,id,status='ready_for_human_review',brand='ClassScout',updated='2026-10-30T10:00:00+00:00'):
  with worker.database() as db:db.execute('INSERT INTO entities VALUES(?,?,?,?,?,?,?)',(id,brand,'https://example.org/'+id,'Name '+id,status,'issue-'+id,updated))
 def take(self,limit=5,status='ready_for_human_review',**kw):
  with worker.database() as db:return [r['id'] for r in candidates.take(db,status,limit,**kw)]
 def test_never_touched_candidates_go_first_oldest_research_first(self):
  self.add('b',updated='2026-10-30T12:00:00+00:00');self.add('a',updated='2026-10-30T09:00:00+00:00');self.add('c',updated='2026-10-30T11:00:00+00:00')
  self.assertEqual(self.take(2),['a','c'])
  self.assertEqual(self.take(2),['b','a'])
 def test_every_candidate_is_visited_before_any_is_visited_again(self):
  for n in range(12):self.add('c%02d'%n,updated='2026-10-30T10:%02d:00+00:00'%n)
  seen=[]
  for _ in range(3):seen+=self.take(4)
  self.assertEqual(sorted(seen),['c%02d'%n for n in range(12)])
  self.assertEqual(self.take(1),[seen[0]])
 def test_a_new_candidate_is_taken_before_ones_already_touched(self):
  for id in ['a','b','c']:self.add(id)
  self.take(3);self.add('new')
  self.assertEqual(self.take(1),['new'])
 def test_only_the_requested_status_and_brand_are_taken_and_stamped(self):
  self.add('ready');self.add('weak',status='needs_more_evidence');self.add('other',brand='Sportolok')
  self.assertEqual(self.take(10),['ready'])
  with worker.database() as db:
   self.assertIsNotNone(candidates.last_touched(db,'ready'));self.assertIsNone(candidates.last_touched(db,'weak'));self.assertIsNone(candidates.last_touched(db,'other'))
 def test_an_extra_condition_filters_before_the_limit(self):
  for id in ['a','b','c']:self.add(id)
  self.assertEqual(self.take(2,where="AND e.id<>?",args=('a',)),['b','c'])
 def test_a_database_without_the_table_is_upgraded_on_first_use(self):
  self.add('a')
  with worker.database() as db:
   self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='candidate_touches'").fetchone())
   self.assertEqual([r['id'] for r in candidates.take(db,'ready_for_human_review',1)],['a'])
   self.assertIsNotNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='candidate_touches'").fetchone())
 def test_entities_are_left_unchanged_by_touching(self):
  self.add('a')
  with worker.database() as db:before=tuple(db.execute('SELECT * FROM entities').fetchone())
  self.take(1)
  with worker.database() as db:self.assertEqual(tuple(db.execute('SELECT * FROM entities').fetchone()),before)

class QueueRotationTests(unittest.TestCase):
 config={'company_id':'company','projects':{'project':'ClassScout'},'agents':{'quality':{'role':'quality'}}}
 def setUp(self):self.helper=test_operations.OperationalTests();self.helper.setUp()
 def tearDown(self):self.helper.tearDown()
 def add(self,id,status='ready_for_human_review',updated='2026-10-30T10:00:00+00:00'):
  with worker.database() as db:db.execute('INSERT INTO entities VALUES(?,?,?,?,?,?,?)',(id,'ClassScout','https://example.org/'+id,'Name '+id,status,'issue-'+id,updated))
 def board(self,fail=()):
  board=Mock()
  def call(path,body=None,method=None):
   if path.startswith('/issues/'):
    if path[len('/issues/'):] in fail:raise RuntimeError('Paperclip is unavailable')
    return {'id':path,'companyId':'company','projectId':'project','title':'Draft','description':''}
   return {'id':'child','identifier':'NAR-child'}
  board.call.side_effect=call;return board
 def queue(self,board):return pipeline.run_queue({'id':'queue','projectId':'project','title':'Queue'},board,self.config,Mock(),worker.database,{})
 def checked(self,board):return [c.args[0][len('/issues/'):] for c in board.call.call_args_list if c.args[0].startswith('/issues/')]
 def test_the_publication_queue_walks_through_all_ready_drafts_without_repeating(self):
  for n in range(12):self.add('c%02d'%n,updated='2026-10-30T10:%02d:00+00:00'%n)
  order=[]
  for _ in range(3):
   board=self.board();self.queue(board);order+=self.checked(board)
  self.assertEqual(len(set(order[:12])),12)
  self.assertEqual(order[12:],order[:3])
 def test_a_draft_that_makes_the_queue_fail_does_not_keep_the_slot(self):
  for n in range(12):self.add('c%02d'%n,updated='2026-10-30T10:%02d:00+00:00'%n)
  with self.assertRaises(RuntimeError):self.queue(self.board(fail={'issue-c00'}))
  board=self.board();self.queue(board)
  self.assertNotIn('issue-c00',self.checked(board));self.assertEqual(self.checked(board),['issue-c%02d'%n for n in range(5,10)])
 def test_the_evidence_queue_does_not_loop_on_a_test_draft(self):
  self.add('a',status='needs_more_evidence',updated='2026-10-30T09:00:00+00:00');self.add('b',status='needs_more_evidence',updated='2026-10-30T10:00:00+00:00');self.add('c',status='needs_more_evidence',updated='2026-10-30T11:00:00+00:00')
  def board():
   board=Mock()
   def call(path,body=None,method=None):
    if path.startswith('/issues/'):return {'id':path,'title':'[Factory test] Research' if path.endswith('issue-a') else 'Research','description':''}
    return {'id':'child-'+body['idempotencyKey'],'identifier':'NAR-'+body['parentId']}
   board.call.side_effect=call;return board
  run=lambda b:evidence.run_queue({'id':'queue','projectId':'project','title':'Queue'},b,self.config,Mock(),worker.database,{})
  first=board();run(first)
  second=board();run(second)
  asked=[c.args[0] for c in second.call.call_args_list if c.args[0].startswith('/issues/')]
  self.assertEqual(asked[0],'/issues/issue-c')
if __name__=='__main__':unittest.main()
