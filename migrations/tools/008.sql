-- A browser Run can encounter several independently approved network requests.
-- Each approval keeps its own PK, immutable request hash and action:<id> effect key.
-- Preserve one-action-per-Run uniqueness for connector/calendar operations.
DROP INDEX approval_run;
CREATE UNIQUE INDEX approval_run ON approvals(run_id)
 WHERE run_id IS NOT NULL AND kind <> 'browser.request';
CREATE INDEX browser_approval_run ON approvals(run_id)
 WHERE run_id IS NOT NULL AND kind = 'browser.request';
