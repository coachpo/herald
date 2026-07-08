CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    family_id UUID NOT NULL,
    replaced_by_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    last_used_at TIMESTAMPTZ NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    revoked_reason TEXT NULL,
    ip TEXT NULL,
    user_agent TEXT NULL
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_family ON refresh_tokens (family_id);

CREATE TABLE ingest_endpoints (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    key_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NULL,
    deleted_at TIMESTAMPTZ NULL,
    last_used_at TIMESTAMPTZ NULL
);
CREATE INDEX idx_ingest_endpoints_user_created ON ingest_endpoints (user_id, created_at DESC);

CREATE TABLE channels (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    config_json_encrypted TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    disabled_at TIMESTAMPTZ NULL
);
CREATE INDEX idx_channels_user_created ON channels (user_id, created_at DESC);

CREATE TABLE rules (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    filter_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    payload_template_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_rules_user_created ON rules (user_id, created_at DESC);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ingest_endpoint_id UUID NOT NULL REFERENCES ingest_endpoints(id) ON DELETE CASCADE,
    received_at TIMESTAMPTZ NOT NULL,
    title TEXT NULL,
    body TEXT NOT NULL,
    "group" TEXT NULL,
    priority INTEGER NOT NULL DEFAULT 3,
    tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    url TEXT NULL,
    extras_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_type TEXT NULL,
    body_sha256 TEXT NOT NULL,
    headers_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    query_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    remote_ip TEXT NULL,
    user_agent TEXT NULL,
    relay_via TEXT NULL,
    deleted_at TIMESTAMPTZ NULL
);
CREATE INDEX idx_messages_user_received ON messages (user_id, received_at DESC);
CREATE INDEX idx_messages_endpoint ON messages (ingest_endpoint_id);

CREATE TABLE deliveries (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    rule_id UUID NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NULL,
    sent_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    provider_response_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_deliveries_message_status ON deliveries (message_id, status);
CREATE INDEX idx_deliveries_next_attempt ON deliveries (status, next_attempt_at);
