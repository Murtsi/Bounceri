-- Pseudonymous collection consent is separate from simulator truth labels.
CREATE TABLE IF NOT EXISTS study_subjects (
    subject_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    withdrawn_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS study_enrollments (
    enrollment_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES study_subjects(subject_id),
    source_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS study_session_reviews (
    review_id TEXT PRIMARY KEY,
    enrollment_id TEXT NOT NULL REFERENCES study_enrollments(enrollment_id),
    external_session_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    digest TEXT NOT NULL,
    behavior TEXT NOT NULL,
    intent TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    UNIQUE (enrollment_id, external_session_id, revision)
);
