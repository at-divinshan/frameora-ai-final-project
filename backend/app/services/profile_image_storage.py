"""Private, immutable image files. Only opaque server-generated keys reach storage."""

import io
import os
from pathlib import Path
import re
import secrets
import stat
import warnings

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

MAX_UPLOAD = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_STORED = 2 * 1024 * 1024
KEY = re.compile(r"[0-9a-f]{64}\.png\Z")


def invalid_image():
    return HTTPException(422, "Upload a valid, non-animated JPEG or PNG image of at most 16 megapixels.")


def normalize_image(data: bytes) -> bytes:
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Profile pictures must not exceed 5 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ("JPEG", "PNG") or getattr(source, "n_frames", 1) != 1:
                    raise invalid_image()
                if source.width * source.height > MAX_PIXELS:
                    raise invalid_image()
                source.verify()
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((512, 512), Image.Resampling.LANCZOS)
                pixels = oriented.convert("RGBA")
                # Rebuild from pixels: no EXIF, text, ICC profile or original metadata survives.
                clean = Image.frombytes("RGBA", pixels.size, pixels.tobytes())
                output = io.BytesIO()
                clean.save(output, format="PNG")
                return output.getvalue()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise invalid_image() from None


def storage_root() -> Path:
    root = Path(settings.profile_image_dir).expanduser()
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


def valid_key(key: str | None) -> bool:
    return isinstance(key, str) and KEY.fullmatch(key) is not None


def write_image(data: bytes) -> str:
    root = storage_root()
    key = secrets.token_hex(32) + ".png"
    path = root / key
    # Never overwrite another image or follow a link.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return key


def delete_image(key: str | None):
    if valid_key(key):
        (storage_root() / key).unlink(missing_ok=True)


def read_image(key: str | None) -> bytes:
    if not valid_key(key):
        raise FileNotFoundError()
    fd = os.open(storage_root() / key, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise FileNotFoundError()
        data = file.read(MAX_STORED + 1)
        if len(data) > MAX_STORED or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise FileNotFoundError()
        return data
