import logging
import sys
from pathlib import Path

# Make server code importable without modifying server files
server_dir = Path(__file__).parent.parent.parent / "server"
sys.path.insert(0, str(server_dir))

from src.db.connection import get_db_connection
from store import store_data

logging.getLogger("ingestor").setLevel(logging.INFO)


def main():
    logging.info("Starting ingestor...")
    db_conn = get_db_connection()

    # 1. Store data
    store_data(db_conn)


if __name__ == "__main__":
    main()
    logging.info("Ingestor finished.")
