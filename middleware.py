import time, json, threading, functools
from config import RATE_LIMIT_PER_MIN, AUDIT_LOG

class RateLimitError(Exception): pass

class RateLimiter:
    def __init__(self, per_min):
        self.cap, self.rate, self.b, self.lock = per_min, per_min / 60, {}, threading.Lock()
    def check(self, key):
        with self.lock:
            tokens, last = self.b.get(key, (self.cap, time.time()))
            now = time.time(); tokens = min(self.cap, tokens + (now - last) * self.rate)
            if tokens < 1: raise RateLimitError(f"Rate limit hit for '{key}'. Try again shortly.")
            self.b[key] = (tokens - 1, now)

limiter = RateLimiter(RATE_LIMIT_PER_MIN)

def audit(event, **data):
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **data}) + "\n")

def middleware(key_arg=0):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **kw):
            key = a[key_arg] if len(a) > key_arg else fn.__name__
            limiter.check(str(key))
            audit("start", fn=fn.__name__, args=str(a)[:300], kw=str(kw)[:300])
            try:
                out = fn(*a, **kw); audit("ok", fn=fn.__name__); return out
            except Exception as e:
                audit("error", fn=fn.__name__, error=str(e)); raise
        return wrap
    return deco
