-- Run outside a business transaction; abort rather than wait behind active writes.
SET lock_timeout = '2s';
SET statement_timeout = '15s';
CREATE INDEX IF NOT EXISTS heartbeat_runs_company_text_id_idx
  ON public.heartbeat_runs (company_id, (id::text));
CREATE INDEX IF NOT EXISTS heartbeat_runs_company_native_context_issue_idx
  ON public.heartbeat_runs
  (company_id, (coalesce(native_issue_id::text, context_snapshot->>'issueId')), created_at DESC);
CREATE INDEX IF NOT EXISTS heartbeat_runs_company_context_issue_task_idx
  ON public.heartbeat_runs
  (company_id, (coalesce(context_snapshot->>'issueId', context_snapshot->>'taskId')), created_at DESC);
CREATE INDEX IF NOT EXISTS heartbeat_runs_company_context_native_issue_idx
  ON public.heartbeat_runs
  (company_id, (coalesce(context_snapshot->>'issueId', context_snapshot->>'taskId', native_issue_id::text)), created_at DESC, id DESC);
