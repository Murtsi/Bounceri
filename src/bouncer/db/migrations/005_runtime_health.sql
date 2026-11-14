-- Operational metadata is distinct from evidence and model capability declarations.
CREATE TABLE runtime_component_health (
    source_id TEXT NOT NULL,
    component TEXT NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL,
    state TEXT NOT NULL,
    config_key TEXT,
    PRIMARY KEY (source_id, component)
);
