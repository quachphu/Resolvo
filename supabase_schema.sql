-- Run this in your Supabase SQL Editor before starting Resolvo.

CREATE TABLE IF NOT EXISTS incidents (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  status            TEXT        NOT NULL DEFAULT 'INVESTIGATING',
  source            TEXT,
  service           TEXT        NOT NULL,
  severity          TEXT        NOT NULL,
  title             TEXT        NOT NULL,
  description       TEXT,
  namespace         TEXT        DEFAULT 'default',
  pod_name          TEXT,
  deployment_name   TEXT,
  reasoning_trace   JSONB       DEFAULT '[]'::jsonb,
  root_cause        TEXT,
  root_cause_type   TEXT,
  confidence_score  INTEGER,
  blast_radius      TEXT,
  remediation_action TEXT,
  remediation_result TEXT,
  slack_message_sent BOOLEAN    DEFAULT FALSE,
  pr_url            TEXT,
  postmortem        TEXT,
  kubectl_command   TEXT,
  cost_estimate     FLOAT,
  started_at        TIMESTAMPTZ DEFAULT NOW(),
  resolved_at       TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Row-level security (open for hackathon — tighten for production)
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all" ON incidents FOR ALL USING (true);

-- Enable Supabase realtime for live dashboard updates
ALTER PUBLICATION supabase_realtime ADD TABLE incidents;
