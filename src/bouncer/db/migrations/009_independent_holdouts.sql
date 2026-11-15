CREATE TABLE IF NOT EXISTS independent_holdouts (
    holdout_id UUID PRIMARY KEY,
    bundle_digest TEXT NOT NULL UNIQUE,
    author_ref TEXT,
    permission_ref TEXT,
    independence_ref TEXT,
    declared_independent BOOLEAN NOT NULL CHECK (declared_independent = true),
    sealed_at TIMESTAMPTZ NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('sealed','revealed','revoked')),
    preparation_id TEXT REFERENCES evaluation_preparations(preparation_id),
    artifact_digest TEXT,
    revealed_at TIMESTAMPTZ,
    bundle BYTEA CHECK (bundle IS NULL OR length(bundle) BETWEEN 1 AND 16777216),
    CHECK ((state = 'revoked' AND author_ref IS NULL AND permission_ref IS NULL
            AND independence_ref IS NULL AND bundle IS NULL) OR
           (state <> 'revoked' AND author_ref IS NOT NULL AND permission_ref IS NOT NULL
            AND independence_ref IS NOT NULL)),
    CHECK ((state = 'sealed' AND preparation_id IS NULL AND artifact_digest IS NULL
            AND revealed_at IS NULL AND bundle IS NULL) OR
           (state = 'revealed' AND preparation_id IS NOT NULL AND artifact_digest IS NOT NULL
            AND revealed_at IS NOT NULL AND bundle IS NOT NULL) OR state = 'revoked')
);
