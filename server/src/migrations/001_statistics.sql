CREATE TABLE IF NOT EXISTS statistics (
    id SERIAL PRIMARY KEY,
    search_query TEXT NOT NULL,
    llm_response TEXT NOT NULL,
    results JSONB NOT NULL,
    execution_time_ms INTEGER NOT NULL,
    is_modified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);