"""Configure Cognee to use the project directory for persistent storage.

Must be called before any cognee operations — the knowledge graph and vector
stores are saved to ./cognee_data/ so they persist across runs without
rebuilding (which costs ~$0.50 in LLM API calls).
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
COGNEE_DATA_DIR = PROJECT_ROOT / "cognee_data"
COGNEE_SYSTEM_DIR = COGNEE_DATA_DIR / ".cognee_system"


def configure_cognee():
    """Point Cognee storage at the project directory and set LLM/embedding config."""
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")

    COGNEE_DATA_DIR.mkdir(exist_ok=True)
    (COGNEE_SYSTEM_DIR / "databases").mkdir(parents=True, exist_ok=True)

    import cognee

    cognee.config.data_root_directory(str(COGNEE_DATA_DIR))
    cognee.config.system_root_directory(str(COGNEE_SYSTEM_DIR))

    cognee.config.set_llm_config({
        "llm_provider": os.getenv("LLM_PROVIDER", "anthropic"),
        "llm_model": os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001"),
        "llm_api_key": os.getenv("LLM_API_KEY"),
        "llm_temperature": float(os.getenv("LLM_TEMPERATURE", "0.0")),
    })

    cognee.config.set_embedding_config({
        "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "fastembed"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        "embedding_dimensions": int(os.getenv("EMBEDDING_DIMENSIONS", "384")),
    })

    # Ensure graph engine picks up new paths
    from cognee.infrastructure.databases.graph.config import get_graph_config
    from cognee.infrastructure.databases.relational.config import get_relational_config

    db_dir = str(COGNEE_SYSTEM_DIR / "databases")
    get_graph_config().graph_file_path = os.path.join(db_dir, get_graph_config().graph_filename)
    get_relational_config().db_path = db_dir

    return cognee
