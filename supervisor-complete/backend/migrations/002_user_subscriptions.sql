-- Migration 002: User Subscriptions table for Stripe billing lifecycle
-- Tracks user tier, subscription status, and Stripe metadata.

-- ============================================================================
-- USER SUBSCRIPTIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    stripe_customer_id TEXT NOT NULL UNIQUE,
    user_id TEXT,
    tier TEXT NOT NULL DEFAULT 'free',
    subscription_id TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    cancel_at_period_end BOOLEAN DEFAULT false,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_customer
    ON user_subscriptions(stripe_customer_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user
    ON user_subscriptions(user_id);

-- RLS: service role only (webhook-driven, no direct user access)
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY subscriptions_service_role ON user_subscriptions
    FOR ALL USING (auth.role() = 'service_role');

-- Version tracking
INSERT INTO schema_migrations (version, description)
VALUES ('002', 'User subscriptions table for Stripe billing lifecycle')
ON CONFLICT (version) DO NOTHING;
