CREATE TABLE IF NOT EXISTS statistics (
    id SERIAL PRIMARY KEY,
    search_query TEXT NOT NULL,
    structured_data JSONB NOT NULL, -- Extracted structured data from the search query (LLM or modified by user)
    results JSONB NOT NULL,
    execution_time_ms INTEGER NOT NULL,
    is_modified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);