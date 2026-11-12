CREATE INDEX IF NOT EXISTS runs_issue_started_idx ON runs(issue_id,started_at DESC);
