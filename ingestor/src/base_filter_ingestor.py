"""
Shared workflow for filter ingestors.
"""

import logging
import re
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from typing import Any

from sentence_transformers import SentenceTransformer


class BaseFilterIngestor:
    """Base workflow for extracting filters from document metadata."""

    logger = logging.getLogger("BaseFilterIngestor")
    PUBLICATION_ROOT_KEY = "collection"

    def __init__(
        self,
        db_conn_factory: Callable[[], AbstractContextManager[Any]],
        settings,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        self.settings = settings
        self.encoder = SentenceTransformer(settings.embedding_model_path, device="cpu")

    @staticmethod
    def camel_case_to_spaces(text: str) -> str:
        """Convert CamelCase to space separated words."""
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)

    @classmethod
    def normalize_filter_key(cls, filter_key: str) -> str:
        """Normalize filter key by converting various casings and delimiters to lowercase spaces."""
        normalized = cls.camel_case_to_spaces(filter_key)
        normalized = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", normalized)
        return normalized.replace("_", " ").replace("/", " ").replace(".", " ").lower()

    @staticmethod
    def safe_strip(value: Any) -> Any:
        """Safely strip strings; pass through None and non-strings."""
        return str(value).strip() if value is not None else value

    @classmethod
    def flatten_json(
        cls, data: Any, parent_key: str = "", sep: str = "."
    ) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        if isinstance(data, dict):
            if "v" in data and "u" in data:
                items.append((parent_key, {"value": data["v"], "unit": data["u"]}))
            elif "value" in data and "unit" in data:
                items.append(
                    (parent_key, {"value": data["value"], "unit": data["unit"]})
                )
            elif "value" in data and "units" in data and "name" in data:
                items.append(
                    (
                        parent_key + sep + data["name"],
                        {"value": data["value"], "unit": data["units"]},
                    )
                )
            else:
                for key, value in data.items():
                    new_key = f"{parent_key}{sep}{key}" if parent_key else key
                    items.extend(cls.flatten_json(value, new_key, sep=sep))
        elif isinstance(data, list):
            for value in data:
                items.extend(cls.flatten_json(value, parent_key, sep=sep))
        else:
            items.append((parent_key, {"value": data, "unit": None}))
        return items

    def fetch_documents_without_filters(
        self, cursor
    ) -> list[tuple[int, dict[str, Any]]]:
        raise NotImplementedError

    def build_filters(
        self, doc_id: int, raw: dict[str, Any]
    ) -> tuple[list[tuple], list[str]]:
        raise NotImplementedError

    def build_filter_rows(
        self, doc_id: int, filters: list[tuple[str, dict[str, Any]]]
    ) -> tuple[list[tuple], list[str]]:
        filter_rows: list[tuple] = []
        keys: list[str] = []
        seen_rows: set[tuple[str, Any, Any, str]] = set()
        for prop, item in filters:
            if not prop or prop.strip() == "":
                continue
            row = (prop, self.safe_strip(item["value"]), item["unit"], "EXPLICIT")
            if row in seen_rows:
                continue
            seen_rows.add(row)
            filter_rows.append((doc_id, *row))
            keys.append(prop)
        return filter_rows, keys

    def insert_filters(self, cursor, filter_rows: list[tuple]) -> None:
        if filter_rows:
            cursor.executemany(
                """
                INSERT INTO filter (document_id, key, value, unit, type)
                VALUES (%s, %s, %s, %s, %s)
                """,
                filter_rows,
            )

    def insert_filter_keys_with_embeddings(self, cursor, keys: Iterable[str]) -> None:
        """
        Normalize filter keys, generate embeddings, and insert into filter_key table.

        Args:
            cursor: Database cursor for executing SQL
            keys: Iterable of filter key names to process
        """
        unique_keys = list(set(keys))
        if not unique_keys:
            return

        normalized = [self.normalize_filter_key(key) for key in unique_keys]
        vectors = self.encoder.encode(normalized)
        if hasattr(vectors, "tolist"):
            vectors = vectors.tolist()
        key_embeddings = list(zip(unique_keys, vectors, strict=True))
        cursor.executemany(
            """
            INSERT INTO filter_key (name, name_vector)
            VALUES (%s, %s)
            ON CONFLICT (name) DO NOTHING
            """,
            key_embeddings,
        )

    BATCH_SIZE = 100

    def process_documents(self, documents: list[tuple[int, dict[str, Any]]]) -> None:
        """Insert flattened metadata filters and corresponding key embeddings."""
        with self.db_conn_factory() as conn:
            with conn.cursor() as cursor:
                batch_rows: list[tuple] = []
                batch_keys: list[str] = []
                for i, (doc_id, raw) in enumerate(documents):
                    self.logger.info("Store filters for document ID: %s", doc_id)
                    rows, keys = self.build_filters(doc_id, raw)
                    batch_rows.extend(rows)
                    batch_keys.extend(keys)
                    if (i + 1) % self.BATCH_SIZE == 0:
                        self.insert_filters(cursor, batch_rows)
                        self.insert_filter_keys_with_embeddings(cursor, batch_keys)
                        conn.commit()
                        self.logger.info(
                            "Committed batch ending at document ID: %s", doc_id
                        )
                        batch_rows = []
                        batch_keys = []
                if batch_rows or batch_keys:
                    self.insert_filters(cursor, batch_rows)
                    self.insert_filter_keys_with_embeddings(cursor, batch_keys)
            conn.commit()

    def run(self) -> None:
        try:
            with self.db_conn_factory() as conn, conn.cursor() as cursor:
                documents = self.fetch_documents_without_filters(cursor)
            self.process_documents(documents)
        except Exception as error:
            self.logger.exception("Error during populating filter table: %s", error)
            raise
