-- Supervisor Backend: Initial Schema
-- Run this in your Supabase SQL editor to create all required tables.
-- Each table uses RLS (Row Level Security) for tenant isolation.

-- ============================================================================
-- CAMPAIGNS
-- ============================================================================
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    memory JSONB NOT NULL DEFAULT '{}',
    profile_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_user_id ON campaigns(user_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);

ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;

CREATE POLICY campaigns_user_isolation ON campaigns
    FOR ALL USING (auth.uid()::TEXT = user_id);

CREATE POLICY campaigns_service_role ON campaigns
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- AGENT RUNS
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    final_output TEXT DEFAULT '',
    memory_extracted JSONB DEFAULT '{}',
    total_iterations INT DEFAULT 0,
    total_duration_ms INT DEFAULT 0,
    providers_used TEXT[] DEFAULT '{}',
    error TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_campaign ON agent_runs(campaign_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_id);

-- ============================================================================
-- APPROVAL QUEUE
-- ============================================================================
CREATE TABLE IF NOT EXISTS approval_queue (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT '',
    action_type TEXT NOT NULL DEFAULT '',
    content JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    decided_by TEXT DEFAULT '',
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approvals_status ON approval_queue(status);
CREATE INDEX IF NOT EXISTS idx_approvals_campaign ON approval_queue(campaign_id);

-- ============================================================================
-- APPROVAL AUDIT LOG
-- ============================================================================
CREATE TABLE IF NOT EXISTS approval_audit_log (
    id BIGSERIAL PRIMARY KEY,
    item_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT DEFAULT '',
    meta JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_item ON approval_audit_log(item_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON approval_audit_log(actor);

-- ============================================================================
-- SPEND LOG
-- ============================================================================
CREATE TABLE IF NOT EXISTS spend_log (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT '',
    amount NUMERIC(12, 4) NOT NULL DEFAULT 0,
    tool TEXT DEFAULT '',
    description TEXT DEFAULT '',
    approved_by TEXT DEFAULT 'auto',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_spend_campaign ON spend_log(campaign_id);

-- ============================================================================
-- CAMPAIGN GENOME (cross-campaign intelligence)
-- ============================================================================
CREATE TABLE IF NOT EXISTS campaign_genome (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    icp_type TEXT DEFAULT '',
    service_type TEXT DEFAULT '',
    geography TEXT DEFAULT '',
    channel_mix JSONB DEFAULT '{}',
    outcomes JSONB DEFAULT '{}',
    lessons JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_genome_campaign ON campaign_genome(campaign_id);
CREATE INDEX IF NOT EXISTS idx_genome_icp ON campaign_genome(icp_type);

-- ============================================================================
-- EVENTS (event bus)
-- ============================================================================
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL DEFAULT '',
    source_agent TEXT DEFAULT '',
    campaign_id TEXT DEFAULT '',
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_campaign ON events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC);

-- ============================================================================
-- PERFORMANCE EVENTS (webhook data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS performance_events (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    event_type TEXT DEFAULT '',
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_perf_campaign ON performance_events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_perf_source ON performance_events(source);

-- ============================================================================
-- ONBOARDING PROFILES
-- ============================================================================
CREATE TABLE IF NOT EXISTS onboarding_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    business_brief JSONB DEFAULT '{}',
    visual_dna JSONB DEFAULT '{}',
    formation JSONB DEFAULT '{}',
    revenue_model JSONB DEFAULT '{}',
    channels JSONB DEFAULT '{}',
    market_research JSONB DEFAULT '{}',
    autonomy JSONB DEFAULT '{}',
    current_stage INT DEFAULT 1,
    completed_stages INT[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_user ON onboarding_profiles(user_id);

ALTER TABLE onboarding_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY onboarding_user_isolation ON onboarding_profiles
    FOR ALL USING (auth.uid()::TEXT = user_id);

CREATE POLICY onboarding_service_role ON onboarding_profiles
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- AGENT BUDGETS
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_budgets (
    campaign_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    allocated NUMERIC(12, 2) DEFAULT 0,
    spent NUMERIC(12, 2) DEFAULT 0,
    period TEXT DEFAULT 'monthly',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (campaign_id, agent_id)
);

-- ============================================================================
-- AGENT RUN SNAPSHOTS (adaptive learning trends)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_run_snapshots (
    id BIGSERIAL PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    score NUMERIC(5, 2) DEFAULT 0,
    duration_ms INT DEFAULT 0,
    iterations INT DEFAULT 0,
    provider TEXT DEFAULT '',
    model TEXT DEFAULT '',
    meta JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_campaign_agent
    ON agent_run_snapshots(campaign_id, agent_id);

-- ============================================================================
-- SCHEMA VERSION TRACKING
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    description TEXT DEFAULT ''
);

INSERT INTO schema_migrations (version, description)
VALUES ('001', 'Initial schema with all core tables and RLS policies')
ON CONFLICT (version) DO NOTHING;
