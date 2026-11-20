from io import BytesIO

from PIL import Image, ImageOps

from domain.enums import ProfileImageKind
from domain.errors.users import (
    InvalidProfileImageError,
    ProfileImageTooLargeError,
    UnsupportedProfileImageTypeError,
)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_INPUT_SIDE = 4096
IMAGE_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
OUTPUT_SIZES = {
    ProfileImageKind.AVATAR: (512, 512),
    ProfileImageKind.BACKGROUND: (1920, 1080),
}


def normalize_profile_image(
    payload: bytearray, media_type: str, kind: ProfileImageKind
) -> bytes:
    with BytesIO(payload) as source, BytesIO() as output:
        try:
            with Image.open(source, formats=tuple(IMAGE_FORMATS.values())) as image:
                if image.format != IMAGE_FORMATS[media_type]:
                    raise UnsupportedProfileImageTypeError()
                if max(image.size) > MAX_INPUT_SIDE:
                    raise ProfileImageTooLargeError()
                if getattr(image, "is_animated", False):
                    raise InvalidProfileImageError()
                ImageOps.exif_transpose(image, in_place=True)
                mode = "RGBA" if image.has_transparency_data else "RGB"
                with image.convert(mode) as converted:
                    converted.thumbnail(OUTPUT_SIZES[kind], Image.Resampling.LANCZOS)
                    converted.info.clear()
                    converted.save(output, format="WEBP", quality=85)
        except Image.DecompressionBombError as exc:
            raise ProfileImageTooLargeError() from exc
        except (OSError, SyntaxError, ValueError) as exc:
            raise InvalidProfileImageError() from exc
        return output.getvalue()
