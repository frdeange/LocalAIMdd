-- BMS Operations — Database Schema
-- Applied to: bms_ops database on postgres.db.svc.cluster.local

CREATE TABLE IF NOT EXISTS cases (
    case_id       VARCHAR(12) PRIMARY KEY,  -- BMS-2026-001
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status        VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    priority      VARCHAR(10) NOT NULL DEFAULT 'MEDIUM',
    summary       TEXT NOT NULL,
    coordinates   JSONB,
    metadata      JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS interactions (
    interaction_id  SERIAL PRIMARY KEY,
    case_id         VARCHAR(12) NOT NULL REFERENCES cases(case_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_name      VARCHAR(50) NOT NULL,
    message         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_interactions_case ON interactions(case_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
