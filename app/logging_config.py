import logging
import sys


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )
    # Chroma's own logger is noisy at INFO and unrelated to our app logic.
    logging.getLogger("chromadb").setLevel(logging.WARNING)
