"""Offline broker backup, integrity and restore-generation tools; never replay business effects."""
import argparse
import fcntl
import json
import os
import uuid
from pathlib import Path
from .store import Store
from .contract import iso


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['initialize','check','backup','rotate-generation'])
    parser.add_argument('--database',required=True)
    parser.add_argument('--destination')
    parser.add_argument('--reason')
    args=parser.parse_args()
    path=Path(args.database)
    if args.action=='initialize':
        if not args.reason or not 12<=len(args.reason)<=200:raise SystemExit('Explicit commissioning reason required; initialization is not recovery')
        store=Store(path,initialize=True)
        with store.transaction() as db:db.execute('INSERT INTO meta VALUES(?,?)',('bootstrap_reason',args.reason))
        print('New private broker initialized. Restore existing receipts instead of initializing after state loss.')
        return
    if not path.is_file():raise SystemExit('Existing broker database required')
    store=Store(path)
    if args.action=='check':
        with store.connection() as db:
            integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
            print(json.dumps({'integrity':integrity,'broker_generation':store.generation(db)}))
            if integrity!='ok':raise SystemExit(1)
    elif args.action=='backup':
        if not args.destination:raise SystemExit('New private backup destination required')
        store.backup(args.destination);print('Consistent private backup verified.')
    else:
        if not args.reason or not 12<=len(args.reason)<=200:raise SystemExit('Bounded reconciliation reason required')
        fd=os.open(path.with_suffix('.service.lock'),os.O_CREAT|os.O_RDWR,0o600)
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise SystemExit('Stop broker admission before rotating restore generation')
            with store.transaction() as db:
                db.execute("UPDATE meta SET value=? WHERE key='generation'",(str(uuid.uuid4()),))
                db.execute('INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('restore_review',json.dumps({'at':iso(store.clock()),'reason':args.reason})))
            print('Restore generation rotated. Reconcile receipts, destinations and quota before enabling claims.')
        finally:os.close(fd)


if __name__=='__main__':main()
