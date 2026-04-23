"""
Optional Fernet encryption for RTSP URLs stored in the database.

Set FERNET_KEY in the environment to enable.  Generate a key once with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If FERNET_KEY is not set, encrypt/decrypt are transparent no-ops so the
system works in dev without any key material.
"""
import os

_KEY = os.getenv("FERNET_KEY", "").strip().encode()
_PREFIX = "enc:"

try:
    from cryptography.fernet import Fernet as _Fernet
    _fernet = _Fernet(_KEY) if _KEY else None
except Exception:
    _fernet = None


def encrypt_rtsp_url(url: str) -> str:
    if _fernet is None or url.startswith(_PREFIX):
        return url
    return _PREFIX + _fernet.encrypt(url.encode()).decode()


def decrypt_rtsp_url(url: str) -> str:
    if _fernet is None or not url.startswith(_PREFIX):
        return url
    return _fernet.decrypt(url[len(_PREFIX):].encode()).decode()
