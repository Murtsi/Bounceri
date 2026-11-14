-- Existing investigation/review/budget and demo enforcement tables, preserving create_all types.
CREATE TABLE IF NOT EXISTS investigation_cases (
    id VARCHAR PRIMARY KEY,
    source_key VARCHAR NOT NULL,
    evidence_hash VARCHAR NOT NULL,
    public BOOLEAN NOT NULL,
    payload JSON NOT NULL,
    created_at VARCHAR NOT NULL,
    UNIQUE (source_key, evidence_hash)
);
CREATE TABLE IF NOT EXISTS investigation_assessments (
    id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    job_id VARCHAR,
    stage VARCHAR NOT NULL,
    payload JSON NOT NULL,
    metadata JSON NOT NULL,
    created_at VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS investigation_jobs (
    id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    evidence_hash VARCHAR NOT NULL,
    config_key VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    remaining INTEGER NOT NULL,
    max_requests INTEGER NOT NULL,
    request_count INTEGER NOT NULL,
    worker_id VARCHAR,
    reason VARCHAR NOT NULL,
    created_at VARCHAR NOT NULL,
    UNIQUE (evidence_hash, config_key)
);
CREATE TABLE IF NOT EXISTS investigation_budget (
    id SERIAL PRIMARY KEY,
    spent INTEGER NOT NULL,
    reserved INTEGER NOT NULL,
    executions INTEGER NOT NULL,
    requests INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS investigation_reservations (
    id VARCHAR PRIMARY KEY,
    job_id VARCHAR NOT NULL,
    stage VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    maximum INTEGER NOT NULL,
    actual INTEGER,
    state VARCHAR NOT NULL,
    usage JSON NOT NULL,
    provider_request_id VARCHAR,
    pricing_version VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS demo_enforcement_policies (
    id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    evidence_hash VARCHAR NOT NULL,
    evidence_version INTEGER NOT NULL,
    actor_id VARCHAR NOT NULL,
    scope VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    revoked_at DOUBLE PRECISION,
    expired_at DOUBLE PRECISION,
    approver VARCHAR NOT NULL,
    affected_requests INTEGER NOT NULL,
    allowed_requests INTEGER NOT NULL,
    tokens DOUBLE PRECISION NOT NULL,
    token_updated_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS demo_enforcement_audit (
    id VARCHAR PRIMARY KEY,
    policy_id VARCHAR NOT NULL,
    event VARCHAR NOT NULL,
    at DOUBLE PRECISION NOT NULL,
    details JSON NOT NULL
);
