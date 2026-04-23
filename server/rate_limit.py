import os
from slowapi import Limiter
from slowapi.util import get_remote_address

_redis_url = os.getenv("REDIS_URL", "")
_storage = f"redis://{_redis_url.split('://')[-1]}" if _redis_url else "memory://"

limiter = Limiter(key_func=get_remote_address, storage_uri=_storage)
