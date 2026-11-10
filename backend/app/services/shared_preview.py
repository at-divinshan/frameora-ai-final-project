"""Protected previews only. Originals are never changed or returned on failure."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import warnings
from PIL import Image, ImageFilter, ImageOps
from fastapi import HTTPException

# Preview-only tuning. Keep the logo crisp by blurring before compositing it.
PREVIEW_BLUR_RADIUS = 0.55
LOGO_OPACITY = 0.48
# Exact copy of frontend/public/images/logo/logo-icon.png, packaged with backend.
LOGO_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'frameora-logo.png'


def logo_position(size, logo_size, digest):
    width, height = size
    margin = max(1, round(min(size) * 0.025))
    available = max(0, width - logo_size[0] - 2 * margin)
    # Lower-edge placements avoid the usual face area without claiming face detection.
    x = min(max(0, width - logo_size[0]), margin + (digest[0] % 3) * available // 2)
    y = max(0, height - logo_size[1] - margin)
    return x, y


def preview_bytes(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.width * source.height > 16_000_000:
                    raise ValueError()
                image = ImageOps.exif_transpose(source).convert('RGB')
                image.thumbnail((960, 960), Image.Resampling.LANCZOS)
                image = image.filter(ImageFilter.GaussianBlur(PREVIEW_BLUR_RADIUS))
                with Image.open(LOGO_PATH) as asset:
                    logo = asset.convert('RGBA')
                logo.thumbnail((max(1, round(image.width * 0.14)), max(1, round(image.height * 0.12))), Image.Resampling.LANCZOS)
                logo.putalpha(logo.getchannel('A').point(lambda alpha: round(alpha * LOGO_OPACITY)))
                image.paste(logo, logo_position(image.size, logo.size, sha256(raw).digest()), logo)
                # New pixel-only image strips any source EXIF/ICC metadata.
                clean = Image.frombytes('RGB', image.size, image.tobytes())
                output = BytesIO()
                clean.save(output, format='JPEG', quality=72, optimize=True)
                return output.getvalue()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(404, 'Shared preview is unavailable.') from None
