import time, hmac, hashlib
from app.config import config

SECRET = config.ADMIN_PASSWORD or "secret"
TOKEN_LIFETIME = 60*60*8  # 8 hours

def create_token():
    expiry = str(int(time.time() + TOKEN_LIFETIME))
    sig = hmac.new(SECRET.encode(), expiry.encode(), hashlib.sha256).hexdigest()
    return f"{expiry}:{sig}"

def verify_token(token: str):
    try:
        expiry, sig = token.split(":", 1)
        expected = hmac.new(SECRET.encode(), expiry.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return False
        if int(expiry) < int(time.time()):
            return False
        return True
    except Exception:
        return False
