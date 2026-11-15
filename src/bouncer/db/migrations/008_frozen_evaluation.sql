CREATE TABLE IF NOT EXISTS evaluation_preparations (
    preparation_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('reserved','frozen','claimed','complete','unavailable','revoked')),
    descriptor JSONB NOT NULL,
    reservation_digest TEXT NOT NULL,
    artifact_digest TEXT,
    artifacts JSONB NOT NULL,
    report JSONB NOT NULL,
    report_digest TEXT,
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failure_code TEXT
);

CREATE TABLE IF NOT EXISTS evaluation_units (
    unit_hash TEXT PRIMARY KEY,
    usage TEXT NOT NULL CHECK (usage IN ('development','holdout')),
    preparation_id TEXT REFERENCES evaluation_preparations(preparation_id),
    created_at TIMESTAMPTZ NOT NULL,
    CHECK ((usage = 'development' AND preparation_id IS NULL) OR
           (usage = 'holdout' AND preparation_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS evaluation_sources (
    preparation_id TEXT NOT NULL REFERENCES evaluation_preparations(preparation_id),
    source_key TEXT NOT NULL,
    PRIMARY KEY (preparation_id, source_key)
);
CREATE INDEX IF NOT EXISTS evaluation_sources_source_idx ON evaluation_sources (source_key);
