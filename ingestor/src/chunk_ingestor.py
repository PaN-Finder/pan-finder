"""
Populate the `chunk` table based on concatenated document title and text.
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel
from sentence_transformers import SentenceTransformer


class ChunkIngestor:
    """
    Orchestrates retrieving documents without chunks, generating semantic chunks,
    and inserting them into the database.
    """

    logger = logging.getLogger("ChunkIngestor")
    expected_vector_dimension = 384

    def __init__(
        self,
        db_conn_factory: Callable[[], AbstractContextManager[Any]],
        settings,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        self.settings = settings
        # Initialize models once per instance (CPU by default for deterministic server behavior)
        model_path = Path(settings.embedding_model_path)
        if not model_path.exists():
            self.logger.warning("Embedding model path does not exist: %s", model_path)
        self.sentence_transformer = SentenceTransformer(str(model_path), device="cpu")
        embedding_dimension = (
            self.sentence_transformer.get_sentence_embedding_dimension()
        )
        if embedding_dimension != self.expected_vector_dimension:
            raise ValueError(
                f"Embedding model dimension {embedding_dimension} does not match "
                f"database vector dimension {self.expected_vector_dimension}."
            )
        max_tokens = self.sentence_transformer.get_max_seq_length()
        if max_tokens is None:
            raise ValueError(
                "Could not determine max token length from the embedding model."
            )
        self.chunker = HybridChunker(
            tokenizer=HuggingFaceTokenizer.from_pretrained(
                str(model_path),
                max_tokens=max_tokens,
                local_files_only=True,
            )
        )

    def generate_chunks(self, text: str) -> list[str]:
        """Split a document's text into chunks using the configured chunker."""
        if not text.strip():
            return []

        docling_doc = DoclingDocument(name="document")
        docling_doc.add_text(DocItemLabel.TEXT, text)

        return [
            self.chunker.contextualize(chunk)
            for chunk in self.chunker.chunk(dl_doc=docling_doc)
        ]

    def insert_chunks(self, cursor, doc_id: int, chunks: list[str]) -> None:
        """Insert the given chunks into the chunk table with their embeddings."""
        if not chunks:
            return
        vectors = self.sentence_transformer.encode(chunks)

        if hasattr(vectors, "tolist"):
            vectors = vectors.tolist()
        rows = [
            (doc_id, idx, chunk, vector)
            for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        cursor.executemany(
            """
            INSERT INTO chunk (document_id, chunk_number, text, text_vector)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (document_id, chunk_number)
            DO UPDATE SET
                text = EXCLUDED.text,
                text_vector = EXCLUDED.text_vector
            """,
            rows,
        )

    def fetch_documents_without_chunks(self, cursor) -> list[tuple[int, str]]:
        cursor.execute(
            """
            SELECT d.id, concat(d.title, '\n', d.text) AS text
            FROM document d
            LEFT JOIN chunk c ON d.id = c.document_id
            WHERE c.document_id IS NULL
            """
        )
        return cursor.fetchall()

    def process_documents(self, documents: list[tuple[int, str]]) -> None:
        """Generate and insert chunks using parallel chunking and a single encode batch."""
        valid = [(doc_id, text) for doc_id, text in documents if text]
        skipped = len(documents) - len(valid)
        if skipped:
            self.logger.warning("Skipping %d document(s) with no text.", skipped)

        # Step 1: chunk all documents in parallel threads.
        # HybridChunker is stateless for inference; SentenceTransformer releases the
        # GIL during PyTorch ops, so threads give real concurrency here.
        def _chunk(item: tuple[int, str]) -> tuple[int, list[str]]:
            doc_id, text = item
            self.logger.info("Generating chunks for document ID: %s", doc_id)
            return doc_id, self.generate_chunks(text)

        with ThreadPoolExecutor() as pool:
            chunked: list[tuple[int, list[str]]] = list(pool.map(_chunk, valid))

        # Step 2: encode all chunks from all documents in a single batch.
        flat_chunks = [chunk for _, chunks in chunked for chunk in chunks]
        if not flat_chunks:
            return

        flat_vectors = self.sentence_transformer.encode(flat_chunks)
        if hasattr(flat_vectors, "tolist"):
            flat_vectors = flat_vectors.tolist()

        # Step 3: rebuild per-document rows.
        rows: list[tuple] = []
        vector_idx = 0
        for doc_id, chunks in chunked:
            for chunk_num, chunk in enumerate(chunks):
                rows.append((doc_id, chunk_num, chunk, flat_vectors[vector_idx]))
                vector_idx += 1

        # Step 4: single transaction with one batch insert.
        with self.db_conn_factory() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO chunk (document_id, chunk_number, text, text_vector)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (document_id, chunk_number)
                    DO UPDATE SET
                        text = EXCLUDED.text,
                        text_vector = EXCLUDED.text_vector
                    """,
                    rows,
                )
            conn.commit()

    def run(self) -> None:
        """Retrieve documents without chunks and process them."""
        try:
            with self.db_conn_factory() as conn, conn.cursor() as cursor:
                docs = self.fetch_documents_without_chunks(cursor)
            self.process_documents(docs)
        except Exception:
            self.logger.exception("Error during populate_chunk", exc_info=True)
            raise
