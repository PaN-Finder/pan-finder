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
