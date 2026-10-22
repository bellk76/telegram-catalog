ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class ImageValidationError(ValueError):
    pass


class ImageTooLargeError(ImageValidationError):
    pass


class UnsupportedImageTypeError(ImageValidationError):
    pass


class InvalidImageError(ImageValidationError):
    pass


def validate_image(data: bytes, content_type: str, max_bytes: int) -> str:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise UnsupportedImageTypeError(content_type)
    if not data:
        raise InvalidImageError("empty image")
    if len(data) > max_bytes:
        raise ImageTooLargeError("image is too large")
    if detect_image_type(data) != content_type:
        raise InvalidImageError("content does not match declared type")
    return ALLOWED_IMAGE_TYPES[content_type]


def detect_image_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None
