"""Index configured knowledge; embedding requests use the selected provider."""

import json
from pathlib import Path
import sys


def main():
    """Return a visible indexing summary instead of hiding per-file failures."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from rag.vector_store import VectorStoreService
    summary = VectorStoreService().load_document()
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed_files"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
