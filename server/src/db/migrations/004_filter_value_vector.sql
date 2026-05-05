ALTER TABLE public.filter ADD COLUMN IF NOT EXISTS value_vector public.vector(384); -- Embedding vector for semantic similarity search on filter values

CREATE INDEX IF NOT EXISTS filter_value_vector_hnsw_idx ON public.filter USING hnsw (value_vector public.vector_cosine_ops) WHERE (value_vector IS NOT NULL);
