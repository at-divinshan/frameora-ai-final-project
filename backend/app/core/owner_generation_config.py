"""Shared backend/frontend configuration for NEW owner batches only."""
import json
from pathlib import Path

# FINAL PRODUCTION — 8 images / 8 credits — DO NOT DELETE
DEFAULT_BATCH_SIZE = 8
# TEMPORARY TESTING — 2 images / 2 credits
# Restore production by changing studioOwnerBatchSize to 8 in owner-generation.config.json.
def load_batch_size():
    path = Path(__file__).resolve().parents[3] / "owner-generation.config.json"
    values = json.loads(path.read_text()) if path.exists() else {}
    size = values.get("studioOwnerBatchSize", DEFAULT_BATCH_SIZE)
    if type(size) is not int or size not in (2, 8):
        raise ValueError("studioOwnerBatchSize must be 2 or 8")
    return size

BATCH_SIZE = load_batch_size()
