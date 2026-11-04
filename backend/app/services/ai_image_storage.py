"""Private AI PNG storage, using the established immutable-file storage rules."""

import io
import stat
import warnings
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.services import profile_image_storage as existing

MAX_UPLOAD = 5 * 1024 * 1024
MAX_STORED = 12 * 1024 * 1024


def normalize_image(data: bytes) -> bytes:
    if len(data) > MAX_STORED:
        raise HTTPException(413, "Image is too large.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ("PNG", "JPEG", "WEBP") or getattr(source, "n_frames", 1) != 1:
                    raise ValueError()
                if source.width * source.height > 16_000_000:
                    raise ValueError()
                source.verify()
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                pixels = oriented.convert("RGB")
                clean = Image.frombytes("RGB", pixels.size, pixels.tobytes())
                output = io.BytesIO()
                clean.save(output, format="PNG")
                result = output.getvalue()
                if len(result) > MAX_STORED:
                    raise ValueError()
                return result
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "Use a valid non-animated JPEG, PNG or WebP image, up to 16 megapixels.") from None


def storage_root() -> Path:
    root = Path(settings.ai_image_dir).expanduser()
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    if not root.is_absolute() or root.is_symlink():
        raise OSError("Invalid private storage location")
    resolved = root.resolve()
    if resolved != root or resolved.is_relative_to(frontend.resolve()) or any(
        part.lower() in ("public", "static") for part in resolved.parts
    ):
        raise OSError("Storage must be private")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise OSError("Private storage permissions required")
    return root


def write_image(data: bytes) -> str:
    return existing.write_image(data, root=storage_root())


def read_image(key: str) -> bytes:
    return existing.read_image(key, root=storage_root(), max_stored=MAX_STORED)


def delete_image(key: str):
    existing.delete_image(key, root=storage_root())
