from base_filter_ingestor import BaseFilterIngestor


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
