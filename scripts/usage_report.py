"""Read-only report of actual recorded operational metadata, including coverage."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway.metrics import Metrics

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=float, default=12)
    parser.add_argument('--project', choices=['classscout','camera','habigoal','pandora','paperclip'])
    parser.add_argument('--database', default='/var/lib/narimato-gateway/metrics.sqlite3')
    args = parser.parse_args()
    metrics = Metrics.readonly(args.database)
    try:
        print(json.dumps(metrics.summary(args.hours, tenant=args.project), indent=2))
    finally:
        metrics.close()
