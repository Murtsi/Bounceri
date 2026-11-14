-- Review scopes are not physical origins; bind only exact known legacy source keys.
ALTER TABLE investigation_cases ADD COLUMN IF NOT EXISTS source_id VARCHAR;
CREATE INDEX IF NOT EXISTS investigation_cases_source_id_idx ON investigation_cases(source_id);
UPDATE investigation_cases AS cases
SET source_id = cases.source_key
WHERE cases.source_id IS NULL AND EXISTS (
    SELECT 1 FROM traffic_sources AS sources WHERE sources.source_key = cases.source_key
);
