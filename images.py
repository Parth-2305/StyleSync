"""Photo handling: prove it's a real image, shrink it, strip hidden data, store it in Supabase Storage."""
import io
import logging
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError

import db

log = logging.getLogger(__name__)
BUCKET = "garment-images"
MAX_SIDE = 900  # phone photos are 4000px+; 900px looks sharp on a card and loads fast
Image.MAX_IMAGE_PIXELS = 25_000_000  # refuse "decompression bombs" (tiny file that unpacks to gigabytes)


class BadImage(Exception):
    """The upload isn't a usable JPG/PNG/WebP."""


def _to_clean_jpeg(file):
    """Opening with Pillow is the real test: a renamed .exe or .html file fails here,
    whatever its name or browser-reported type says."""
    try:
        img = Image.open(file)
        if img.format not in ("JPEG", "PNG", "WEBP"):
            raise BadImage
        img = ImageOps.exif_transpose(img)  # phones store "rotate me" in metadata; apply it first
        img = img.convert("RGB")            # rebuilding the image drops EXIF, incl. GPS location
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise BadImage from error
    out = io.BytesIO()
    img.save(out, "JPEG", quality=82)  # always re-encode, so we never store the uploader's raw bytes
    return out.getvalue()


def save_photo(file, user_id):
    """Stores the photo as <user_id>/<random>.jpg and returns its public URL."""
    path = f"{user_id}/{uuid.uuid4().hex}.jpg"  # random name: URLs can't be guessed
    bucket = db.data_client().storage.from_(BUCKET)
    bucket.upload(path, _to_clean_jpeg(file), {"content-type": "image/jpeg"})
    return bucket.get_public_url(path)


def delete_photo(url):
    """Best effort: a leftover file is harmless, so a failure is logged, not shown to the user."""
    try:
        db.data_client().storage.from_(BUCKET).remove([url.split(f"/{BUCKET}/")[-1].split("?")[0]])
    except Exception:
        log.exception("could not delete photo")
