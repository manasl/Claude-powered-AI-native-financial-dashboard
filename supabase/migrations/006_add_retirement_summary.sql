-- Add retirement_summary column to analysis_reports
alter table analysis_reports
  add column if not exists retirement_summary jsonb;
