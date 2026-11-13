-- S3: requests / sessions / labels (A). IDs are bigint in DB; Python boundary uses str.

CREATE TABLE IF NOT EXISTS requests (
    id              BIGSERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL,
    ip              INET NOT NULL,
    method          TEXT NOT NULL,
    path            TEXT NOT NULL,
    status          INT NOT NULL,
    user_agent      TEXT NOT NULL DEFAULT '',
    query           TEXT NOT NULL DEFAULT '',
    bytes           INT NOT NULL DEFAULT 0,
    headers         JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_type    TEXT,
    session_id      BIGINT,
    UNIQUE (ts, ip, method, path, status, user_agent)
);

CREATE TABLE IF NOT EXISTS sessions (
    id              BIGSERIAL PRIMARY KEY,
    ip              INET NOT NULL,
    user_agent      TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS sessions_started_at_idx ON sessions (started_at);

CREATE TABLE IF NOT EXISTS labels (
    session_id      BIGINT PRIMARY KEY REFERENCES sessions (id) ON DELETE CASCADE,
    run_id          TEXT NOT NULL,
    sim_class       TEXT NOT NULL,
    campaign_id     TEXT
);

ALTER TABLE requests
    DROP CONSTRAINT IF EXISTS requests_session_id_fkey;
ALTER TABLE requests
    ADD CONSTRAINT requests_session_id_fkey
    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE SET NULL;
