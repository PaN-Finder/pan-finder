import logging
import sys
from pathlib import Path

server_dir = Path(__file__).parent.parent.parent / "server"
sys.path.insert(0, str(server_dir))

from src.db.connection import get_db_connection
from src.config import get_settings
from document_ingestor import DocumentIngestor
from chunk_ingestor import ChunkIngestor
from filter_ingestor import FilterIngestor
from numeric_filter_ingestor import NumericFilterIngestor
from filter_value_converter import FilterValueConverter
from filter_enricher import FilterEnricher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("Ingestor")


def main():
    logging.info("Starting ingestor...")

    settings = get_settings()

    # 1. Store data
    DocumentIngestor(get_db_connection).run()

    # 2. Create chunks
    ChunkIngestor(get_db_connection, settings).run()

    # 3. Populate filters
    FilterIngestor(get_db_connection, settings).run()

    # 4. Derive numeric filters
    NumericFilterIngestor(get_db_connection, settings).run()

    # 5. Convert filter values to structured types
    FilterValueConverter(get_db_connection).run()

    # 6. Enrich filter table with derived publisher data
    FilterEnricher(get_db_connection).run()

    logging.info("Ingestor finished.")


if __name__ == "__main__":
    main()
