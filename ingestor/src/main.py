import logging
import sys
from pathlib import Path

server_dir = Path(__file__).parent.parent.parent / "server"
sys.path.insert(0, str(server_dir))

# ruff: noqa: E402
from chunk_ingestor import ChunkIngestor
from document_ingestor import DocumentIngestor
from filter_description_ingestor import FilterDescriptionIngestor
from filter_enricher import FilterEnricher
from filter_ingestor import FilterIngestor
from filter_value_converter import FilterValueConverter
from filter_vector_ingestor import FilterVectorIngestor
from numeric_filter_ingestor import NumericFilterIngestor
from publication_document_ingestor import PublicationDocumentIngestor
from publication_filter_ingestor import PublicationFilterIngestor
from summary_ingestor import SummaryIngestor

from src.config import get_settings
from src.db.connection import get_database_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("Ingestor")


def main():
    logging.info("Starting ingestor...")

    settings = get_settings()

    # 1.a. Standard document schemas
    DocumentIngestor(get_database_connection).run()

    # 1.b. Publication document schema
    PublicationDocumentIngestor(get_database_connection).run()

    # 2. Create chunks
    ChunkIngestor(get_database_connection, settings).run()

    # 3.a. Populate filters for standard document schemas
    FilterIngestor(get_database_connection, settings).run()

    # 3.b. Populate filters for publication document schema
    PublicationFilterIngestor(get_database_connection, settings).run()

    # 4. Derive numeric filters
    NumericFilterIngestor(get_database_connection, settings).run()

    # 5. Convert filter values to structured types
    FilterValueConverter(get_database_connection).run()

    # 6. Enrich filter table with derived publisher data
    FilterEnricher(get_database_connection, settings).run()

    # 7. Compute embeddings for selected filter values
    FilterVectorIngestor(get_database_connection, settings).run()

    # 8. Populate document summaries
    SummaryIngestor(get_database_connection, settings).run()

    # 9. Populate filter descriptions and embed them
    FilterDescriptionIngestor(get_database_connection, settings).run()

    logging.info("Ingestor finished.")


if __name__ == "__main__":
    main()
