"""Which candidate the system works on next: always the one touched longest ago.

Every candidate (an `entities` row) has a last-touched time in `candidate_touches`. A candidate with no row has
never been touched and goes first. Selecting candidates to work on stamps them in the same transaction, so a
candidate that is blocked, fails or is skipped still moves behind all the others and cannot hold a queue slot in
a loop. The table is separate from `entities` so an older worker can keep reading and writing that table."""
import time

def initialize(db):
 db.execute('CREATE TABLE IF NOT EXISTS candidate_touches(entity_id TEXT PRIMARY KEY,touched_at REAL NOT NULL)')

def touch(db,entity_id,stamp=None):
 """Record that the system just worked on this candidate."""
 initialize(db)
 db.execute('INSERT INTO candidate_touches VALUES(?,?) ON CONFLICT(entity_id) DO UPDATE SET touched_at=excluded.touched_at',(entity_id,stamp or time.time()))

def last_touched(db,entity_id):
 """Seconds since the epoch of the last touch, or None when the candidate has never been touched."""
 initialize(db)
 row=db.execute('SELECT touched_at FROM candidate_touches WHERE entity_id=?',(entity_id,)).fetchone()
 return row[0] if row else None

def take(db,status,limit,brand='ClassScout',where='',args=()):
 """The `limit` candidates with this status that were touched longest ago, stamped as touched now.

 Never-touched candidates come first (oldest research first among them), then the oldest touch. `where` is an extra
 SQL condition on the entities alias `e`, with its parameters in `args`. Returns plain dicts of the entities rows."""
 initialize(db)
 # Take the write lock before reading so two workers cannot pick the same candidates.
 if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
 rows=[dict(r) for r in db.execute('SELECT e.* FROM entities e LEFT JOIN candidate_touches t ON t.entity_id=e.id WHERE e.brand=? AND e.status=? '+where+' ORDER BY t.touched_at IS NOT NULL,t.touched_at,e.updated_at,e.id LIMIT ?',(brand,status,*args,limit))]
 stamp=time.time()
 for row in rows:touch(db,row['id'],stamp)
 return rows
