"""
Populate `document.summary` and `document.title_summary_vector` using Azure OpenAI
and a SentenceTransformer. Fetches documents with `summary IS NULL`, generates a
short summary (fallback to title if text is empty), embeds `title + summary`, and updates the row.
"""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from openai import AzureOpenAI, OpenAI
from sentence_transformers import SentenceTransformer


class SummaryIngestor:
    """Generate summaries and title+summary embeddings and update `document`."""

    logger = logging.getLogger("SummaryIngestor")

    def __init__(
        self,
        db_conn_factory: Callable[[], AbstractContextManager[Any]],
        settings,
        model_name: str | None = None,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        self.settings = settings
        self.model_name = model_name or self.settings.default_model_name
        if settings.llm_provider == "openai":
            self.llm = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        else:
            self.llm = AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
            )
        self.embedder = SentenceTransformer(settings.embedding_model_path, device="cpu")

    def fetch_documents_without_summary(self, cursor) -> list[tuple[int, str, str]]:
        """Return `(id, title, text)` for rows where `summary IS NULL`."""
        cursor.execute(
            """
            SELECT id, title, text FROM document WHERE summary IS NULL
            """
        )
        return cursor.fetchall()

    def generate_summary(self, title: str, text: str) -> str:
        """Generate a short summary; return `title` if `text` is empty."""
        if not text or text.strip() == "":
            return title
        prompt_system = """You write short retrieval text for embedding-based similarity search over scientific documents and datasets.

    Goal:
    - Populate a `summary` field used only for semantic search quality, not for human reading.

    Instructions:
    - Write one compact text block in at most 80 words.
    - Make it dense with the most search-relevant facts explicitly supported by the input.
    - Prefer concrete scientific anchors such as the main topic, organ or specimen, disease or condition, modality, anatomical region, scale or resolution, acquisition details, and notable identifiers.
    - If the input is noisy or repetitive, remove low-signal repetition and keep the strongest retrieval cues.
    - Prefer explicit domain terms and noun phrases over narrative filler.
    - Do not invent, infer, or normalize facts that are not clearly stated.
    - Do not mention missing information.
    - Do not use bullets, labels, markdown, or quotation marks.
    - If you cannot produce text better than the title for search, return the title verbatim.

    Output only the summary text.
    """
        prompt_user = f"<title>\n{title}\n</title>\n\n<text>\n{text}\n</text>"
        resp = self.llm.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": prompt_user},
            ],
            max_completion_tokens=300,
        )
        content = resp.choices[0].message.content if resp and resp.choices else None
        return content or title

    def process_documents(self, documents: list[tuple[int, str, str]]) -> None:
        """Summarize, embed, and persist updates in a single transaction."""
        with self.db_conn_factory() as conn:
            with conn.cursor() as cursor:
                for doc_id, title, text in documents:
                    self.logger.info("Generating summary for document ID: %s", doc_id)
                    summary = self.generate_summary(title, text)
                    self.logger.info("Document ID: %s Summary: %s", doc_id, summary)
                    title_summary_vec = self.embedder.encode(
                        f"{title} {summary}"
                    ).tolist()
                    cursor.execute(
                        """
                        UPDATE document SET summary = %s, title_summary_vector = %s WHERE id = %s;
                        """,
                        (summary, title_summary_vec, doc_id),
                    )
            conn.commit()

    def run(self) -> None:
        """Fetch documents and process them with basic error handling."""
        try:
            with self.db_conn_factory() as conn, conn.cursor() as cursor:
                documents = self.fetch_documents_without_summary(cursor)
            self.process_documents(documents)
        except Exception:
            self.logger.exception("Error during populate_summary", exc_info=True)
            raise
