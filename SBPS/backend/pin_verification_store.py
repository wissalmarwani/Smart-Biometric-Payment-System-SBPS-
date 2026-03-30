import threading
import time


class PinVerificationStore:
    """Stores short-lived PIN verification state per user."""

    def __init__(self, ttl_seconds=300):
        self.ttl_seconds = int(ttl_seconds)
        self._verified_at = {}
        self._lock = threading.Lock()

    def mark_verified(self, user_id):
        with self._lock:
            self._verified_at[str(user_id)] = time.time()

    def has_valid_verification(self, user_id):
        user_key = str(user_id)
        with self._lock:
            verified_at = self._verified_at.get(user_key)
            if not verified_at:
                return False

            if (time.time() - verified_at) > self.ttl_seconds:
                self._verified_at.pop(user_key, None)
                return False

            return True

    def clear(self, user_id):
        with self._lock:
            self._verified_at.pop(str(user_id), None)
