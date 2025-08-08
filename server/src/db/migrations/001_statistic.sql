CREATE TABLE IF NOT EXISTS statistic (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_query TEXT NOT NULL,
    structured_data JSONB NOT NULL, -- Extracted structured data from the search query (LLM or modified by user)
    results JSONB NOT NULL,
    execution_time_ms INTEGER NOT NULL,
    modified_query_id UUID DEFAULT NULL, -- If user modifies the structured data, this will be the ID of the parent query in statistics table
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);