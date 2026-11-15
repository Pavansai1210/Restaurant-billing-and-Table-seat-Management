import io
import uuid

from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 3 * 1024 * 1024
MAX_SIDE = 4000
SHOW_WIDTH = 600


class BadPhoto(Exception):
    pass


def clean_photo(upload):
    """Open the file as a picture, and save it again as a small, clean JPEG."""
    if upload.size > MAX_BYTES:
        raise BadPhoto('The photo is too big. Please use one under 3 MB.')
    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise BadPhoto('This file is not a picture.')
    if max(image.size) > MAX_SIDE:
        raise BadPhoto('The picture is too large. Please use one under 4000 pixels wide.')

    image = image.convert('RGB')                       # also drops any hidden data
    if image.width > SHOW_WIDTH:
        height = round(image.height * SHOW_WIDTH / image.width)
        image = image.resize((SHOW_WIDTH, height))
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=85)
    return ContentFile(buffer.getvalue(), name=f'{uuid.uuid4().hex}.jpg')