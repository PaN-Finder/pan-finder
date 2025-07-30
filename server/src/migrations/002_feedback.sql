CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    statistic_id UUID NOT NULL, -- Reference to the statistic entry
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('positive', 'negative')),
    metadata JSONB, -- Additional metadata about the feedback (doi, positions, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (statistic_id) REFERENCES statistic(id) ON DELETE CASCADE,
    UNIQUE (statistic_id, metadata) -- Ensure uniqueness of feedback for each statistic
);

-- Composite index to speed up queries filtering by statistic_id and metadata together
CREATE INDEX IF NOT EXISTS idx_feedback_statistic_id_metadata ON feedback(statistic_id, metadata);