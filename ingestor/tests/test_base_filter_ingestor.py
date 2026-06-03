from contextlib import nullcontext
from typing import Any, cast

from base_filter_ingestor import BaseFilterIngestor


class _Settings:
    embedding_model_path = "unused"


class _Encoder:
    def __init__(self) -> None:
        self.encoded: list[list[str]] = []

    def encode(self, values: list[str]) -> list[list[float]]:
        self.encoded.append(values)
        return [[float(index)] for index, _ in enumerate(values)]


class _Cursor:
    def __init__(self, existing_keys: set[str]) -> None:
        self.existing_keys = existing_keys
        self.select_params: list[list[str]] = []
        self.inserted_rows: list[tuple[str, list[float]]] = []

    def execute(self, query: str, params: tuple[list[str]]) -> None:
        self.select_params.append(params[0])
        self._rows = [(key,) for key in params[0] if key in self.existing_keys]

    def fetchall(self) -> list[tuple[str]]:
        return self._rows

    def executemany(self, query: str, rows: list[tuple[str, list[float]]]) -> None:
        self.inserted_rows.extend(rows)


def test_normalize_filter_key_splits_letters_and_numbers() -> None:
    assert (
        BaseFilterIngestor.normalize_filter_key("detector02positioners")
        == "detector 02 positioners"
    )


def test_normalize_filter_key_handles_camel_case_with_numbers() -> None:
    assert (
        BaseFilterIngestor.normalize_filter_key("InstrumentDetector02Positioners")
        == "instrument detector 02 positioners"
    )


def test_normalize_filter_key_preserves_existing_delimiter_behavior() -> None:
    assert (
        BaseFilterIngestor.normalize_filter_key(
            "scientificMetadata.measurement/beamline"
        )
        == "scientific metadata measurement beamline"
    )


def test_flatten_json_hoists_wrapper_keys() -> None:
    flattened = BaseFilterIngestor.flatten_json(
        {
            "metadata": {"sampleName": "Quartz"},
            "scientificMetadata": {"measurement": {"beamline": "ID16"}},
            "document": {"title": "Example"},
        }
    )

    assert ("sampleName", {"value": "Quartz", "unit": None}) in flattened
    assert ("measurement.beamline", {"value": "ID16", "unit": None}) in flattened
    assert ("document.title", {"value": "Example", "unit": None}) in flattened


def test_flatten_datasets_preserves_non_wrapper_keys() -> None:
    flattened = BaseFilterIngestor._flatten_datasets(
        [
            {
                "title": "Dataset",
                "metadata": {"sampleName": "Quartz"},
                "scientificMetadata": {"measurement": {"beamline": "ID16"}},
                "instrument": {"name": "Nano"},
            }
        ]
    )

    assert ("title", {"value": "Dataset", "unit": None}) in flattened
    assert ("sampleName", {"value": "Quartz", "unit": None}) in flattened
    assert ("measurement.beamline", {"value": "ID16", "unit": None}) in flattened
    assert ("instrument.name", {"value": "Nano", "unit": None}) in flattened


def test_insert_filter_keys_skips_existing_and_cached_keys() -> None:
    ingestor = BaseFilterIngestor(lambda: nullcontext(), _Settings(), dry_run=True)
    encoder = _Encoder()
    cast(Any, ingestor).encoder = encoder
    cursor = _Cursor({"existing.key"})

    ingestor.insert_filter_keys_with_embeddings(
        cursor, ["existing.key", "newKey", "newKey"]
    )
    ingestor.insert_filter_keys_with_embeddings(cursor, ["existing.key", "newKey"])

    assert cursor.select_params == [["existing.key", "newKey"]]
    assert encoder.encoded == [["new key"]]
    assert cursor.inserted_rows == [("newKey", [0.0])]
