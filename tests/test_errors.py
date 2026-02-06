from app.core.errors import is_heic

def test_is_heic():
    assert is_heic("a.heic")
    assert is_heic("b.HEIF")
    assert not is_heic("c.jpg")
