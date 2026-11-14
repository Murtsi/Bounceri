-- Preserve native response sizes beyond the signed 32-bit range.
ALTER TABLE requests ALTER COLUMN bytes TYPE BIGINT;
