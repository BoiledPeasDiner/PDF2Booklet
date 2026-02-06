class UserFacingError(Exception):
    """UI/CLIでそのまま表示してよいエラー"""

def is_heic(path: str) -> bool:
    p = path.lower()
    return p.endswith(".heic") or p.endswith(".heif")

def is_supported_image(path: str) -> bool:
    p = path.lower()
    return p.endswith(".jpg") or p.endswith(".jpeg") or p.endswith(".png")

def is_pdf(path: str) -> bool:
    return path.lower().endswith(".pdf")
