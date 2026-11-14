-- Preserve normalized traffic and existing bigint relations; external IDs stay opaque strings.
ALTER TABLE sessions ADD COLUMN source_key TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE sessions ADD COLUMN external_id TEXT;
UPDATE sessions SET external_id = id::text;
ALTER TABLE sessions ALTER COLUMN external_id SET NOT NULL;
ALTER TABLE sessions ADD CONSTRAINT sessions_source_external_key UNIQUE (source_key, external_id);
ALTER TABLE sessions ADD COLUMN visible BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE sessions ADD COLUMN view_started_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN view_ended_at TIMESTAMPTZ;
UPDATE sessions SET view_started_at = started_at, view_ended_at = ended_at;
ALTER TABLE sessions ALTER COLUMN view_started_at SET NOT NULL;
ALTER TABLE sessions ALTER COLUMN view_ended_at SET NOT NULL;

ALTER TABLE requests DROP CONSTRAINT IF EXISTS requests_ts_ip_method_path_status_user_agent_key;
ALTER TABLE requests ADD COLUMN username TEXT;
ALTER TABLE requests ADD COLUMN source_key TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE requests ADD COLUMN generation TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE requests ADD COLUMN byte_offset BIGINT;
UPDATE requests SET byte_offset = id;
ALTER TABLE requests ALTER COLUMN byte_offset SET NOT NULL;
ALTER TABLE requests ADD CONSTRAINT requests_source_event_key UNIQUE (source_key, generation, byte_offset);
ALTER TABLE requests ADD COLUMN visible BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE requests ADD COLUMN position BIGINT NOT NULL DEFAULT 0;
CREATE INDEX requests_source_ts_idx ON requests (source_key, ts);
ALTER TABLE labels ADD COLUMN visible BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE traffic_sources (
    source_key TEXT PRIMARY KEY,
    generation TEXT,
    byte_offset BIGINT NOT NULL,
    revision BIGINT NOT NULL,
    snapshot JSONB NOT NULL,
    resume_state JSONB NOT NULL,
    read_only BOOLEAN NOT NULL DEFAULT FALSE
);
INSERT INTO traffic_sources (source_key, generation, byte_offset, revision, snapshot, resume_state)
SELECT DISTINCT source_key, NULL, 0, 0, '{}'::jsonb, '{}'::jsonb FROM sessions;
