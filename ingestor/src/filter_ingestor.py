"""
Populate the `filter` and `filter_key` tables from document raw metadata.
"""

import logging
import re
from typing import Callable, ContextManager, Any, Iterable, List, Tuple, Dict

from sentence_transformers import SentenceTransformer


class FilterIngestor:
    """Extract metadata filters from `document.raw` and persist them."""

    logger = logging.getLogger("FilterIngestor")

    def __init__(
        self,
        db_conn_factory: Callable[[], ContextManager[Any]],
        settings,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        self.settings = settings
        self.encoder = SentenceTransformer(settings.embedding_model_path, device="cpu")

    # --- Normalization helpers ---
    @staticmethod
    def camel_case_to_spaces(text: str) -> str:
        """Convert CamelCase to space separated words."""
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)

    @classmethod
    def normalize_filter_key(cls, filter_key: str) -> str:
        """Normalize filter key by converting various casings and delimiters to lowercase spaces."""
        return (
            cls.camel_case_to_spaces(filter_key)
            .replace("_", " ")
            .replace("/", " ")
            .replace(".", " ")
            .lower()
        )

    @staticmethod
    def safe_strip(value: Any) -> Any:
        """Safely strip strings; pass through None and non-strings."""
        return str(value).strip() if value is not None else value

    @classmethod
    def flatten_json(
        cls, data: Any, parent_key: str = "", sep: str = "."
    ) -> List[Tuple[str, Dict[str, Any]]]:
        items: List[Tuple[str, Dict[str, Any]]] = []
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
                for k, v in data.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    items.extend(cls.flatten_json(v, new_key, sep=sep))
        elif isinstance(data, list):
            for v in data:
                items.extend(cls.flatten_json(v, parent_key, sep=sep))
        else:
            items.append((parent_key, {"value": data, "unit": None}))
        return items

    # --- DB operations ---
    def fetch_documents_without_filters(
        self, cursor
    ) -> List[Tuple[int, Dict[str, Any]]]:
        cursor.execute(
            """
            SELECT d.id, d.raw
            FROM document d
            LEFT JOIN filter f ON d.id = f.document_id
            WHERE f.document_id IS NULL
            """
        )
        return cursor.fetchall()

    def build_filters(
        self, doc_id: int, raw: Dict[str, Any]
    ) -> Tuple[List[Tuple], List[str]]:
        filters = (
            self.flatten_json(raw.get("document", {}))
            + self.flatten_json(raw.get("panosc", {}))
            + self.flatten_json(raw.get("datasets", {}))
            + self.flatten_json(raw.get("datacite", {}))
            + self.flatten_json(raw.get("catalogue", {}))
        )
        filter_rows: List[Tuple] = []
        keys: List[str] = []
        for prop, item in filters:
            if not prop or prop.strip() == "":
                continue
            filter_rows.append(
                (doc_id, prop, self.safe_strip(item["value"]), item["unit"], "EXPLICIT")
            )
            keys.append(prop)
        return filter_rows, keys

    def insert_filters_and_keys(
        self, cursor, filter_rows: List[Tuple], unique_keys: Iterable[str]
    ) -> None:
        if filter_rows:
            cursor.executemany(
                """
                INSERT INTO filter (document_id, key, value, unit, type)
                VALUES (%s, %s, %s, %s, %s)
                """,
                filter_rows,
            )
        # Embeddings for keys (normalized)
        unique_keys = list(set(unique_keys))
        if unique_keys:
            normalized = [self.normalize_filter_key(k) for k in unique_keys]
            vectors = self.encoder.encode(normalized)
            if hasattr(vectors, "tolist"):
                vectors = vectors.tolist()
            key_embeddings = list(zip(unique_keys, vectors))
            cursor.executemany(
                """
                INSERT INTO filter_key (name, name_vector)
                VALUES (%s, %s)
                ON CONFLICT (name) DO NOTHING
                """,
                key_embeddings,
            )

    def process_documents(self, documents: List[Tuple[int, Dict[str, Any]]]) -> None:
        """Insert flattened metadata filters and corresponding key embeddings."""
        with self.db_conn_factory() as conn:
            with conn.cursor() as cursor:
                all_rows: List[Tuple] = []
                all_keys: List[str] = []
                for doc_id, raw in documents:
                    self.logger.info("Store filters for document ID: %s", doc_id)
                    rows, keys = self.build_filters(doc_id, raw)
                    all_rows.extend(rows)
                    all_keys.extend(keys)
                self.insert_filters_and_keys(cursor, all_rows, all_keys)
            conn.commit()

    def run(self) -> None:
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    documents = self.fetch_documents_without_filters(cursor)
            self.process_documents(documents)
        except Exception as e:
            self.logger.exception("Error during populating filter table: %s", e)
            raise
