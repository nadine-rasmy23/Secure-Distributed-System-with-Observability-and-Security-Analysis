-- ============================================
-- Database Schema: Audit Logs & Request States
-- ============================================

-- Audit logs table: stores all events across services
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    service_name VARCHAR(50) NOT NULL,
    request_id UUID NOT NULL,
    action VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failure')),
    source VARCHAR(50) NOT NULL
);

-- Request state tracking table
CREATE TABLE IF NOT EXISTS request_states (
    id SERIAL PRIMARY KEY,
    request_id UUID NOT NULL,
    state VARCHAR(20) NOT NULL CHECK (state IN ('RECEIVED', 'AUTHENTICATED', 'QUEUED', 'CONSUMED', 'PROCESSED', 'FAILED')),
    service_name VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    details TEXT
);

-- Indexes for fast lookups by request_id
CREATE INDEX idx_audit_request_id ON audit_logs(request_id);
CREATE INDEX idx_states_request_id ON request_states(request_id);
