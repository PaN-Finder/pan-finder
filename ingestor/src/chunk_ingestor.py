"""
Populate the `chunk` table based on concatenated document title and text.
"""

from contextlib import AbstractContextManager
import logging
from pathlib import Path
from collections.abc import Callable
from typing import Any

from sentence_transformers import SentenceTransformer
from semantic_chunkers.chunkers import StatisticalChunker
from semantic_router.encoders import HuggingFaceEncoder


class ChunkIngestor:
    """
    Orchestrates retrieving documents without chunks, generating semantic chunks,
    and inserting them into the database.
    """

    logger = logging.getLogger("ChunkIngestor")

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
        self.chunker = StatisticalChunker(
            encoder=HuggingFaceEncoder(name="sentence-transformers/all-MiniLM-L12-v2"),
            enable_statistics=True,
        )

    def generate_chunks(self, text: str) -> list[str]:
        """Split a document's text into chunks using the configured chunker."""
        return self.chunker.splitter(text)

    def insert_chunks(self, cursor, doc_id: int, chunks: list[str]) -> None:
        """Insert the given chunks into the chunk table with their embeddings."""
        if not chunks:
            return
        vectors = self.sentence_transformer.encode(chunks)

        if hasattr(vectors, "tolist"):
            vectors = vectors.tolist()
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            cursor.execute(
                """
                INSERT INTO chunk (document_id, chunk_number, text, text_vector)
                VALUES (%s, %s, %s, %s)
                """,
                (doc_id, idx, chunk, vector),
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
        """Generate and insert chunks for documents in a single transaction."""
        with self.db_conn_factory() as conn:
            with conn.cursor() as cursor:
                for doc_id, text in documents:
                    if not text:
                        self.logger.warning(
                            "Document ID %s has no text. Skipping.", doc_id
                        )
                        continue
                    self.logger.info("Generating chunks for document ID: %s", doc_id)
                    chunks = self.generate_chunks(text)
                    self.insert_chunks(cursor, doc_id, chunks)
            conn.commit()

    def run(self) -> None:
        """Retrieve documents without chunks and process them."""
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    docs = self.fetch_documents_without_chunks(cursor)
            self.process_documents(docs)
        except Exception:
            self.logger.exception("Error during populate_chunk", exc_info=True)
            raise
