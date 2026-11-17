"""Shared batch setting with a checked backend-only deployment copy."""
import json
from pathlib import Path


def load_batch_size():
    backend = Path(__file__).resolve().parents[2]
    packaged = backend / "owner-generation.config.json"
    shared = backend.parent / "owner-generation.config.json"
    # Railway's backend-only context must contain an explicit approved value.
    values = json.loads(packaged.read_text())
    if shared.exists() and json.loads(shared.read_text()) != values:
        raise ValueError("Owner generation configuration copies must match")
    size = values.get("studioOwnerBatchSize")
    if type(size) is not int or size not in (2, 8):
        raise ValueError("studioOwnerBatchSize must be 2 or 8")
    return size


BATCH_SIZE = load_batch_size()
