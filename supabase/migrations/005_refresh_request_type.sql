-- Add request_type to refresh_requests so the daemon knows whether to run
-- only the data-fetch notebooks ("sync") or only the Claude-analysis notebooks ("analyze").

alter table refresh_requests
  add column if not exists request_type text not null default 'sync';

comment on column refresh_requests.request_type is
  'sync = fetch Plaid + enrich (notebooks 02, 02b, 03); analyze = Claude (notebooks 04, 05)';
