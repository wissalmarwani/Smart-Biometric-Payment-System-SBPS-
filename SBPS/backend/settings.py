import os
from dataclasses import dataclass


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


@dataclass(frozen=True)
class AppSettings:
    db_pool_min: int
    db_pool_max: int
    pin_ttl_seconds: int
    max_pin_attempts: int
    pin_lock_seconds: int
    face_distance_threshold: float

    @classmethod
    def from_env(cls):
        return cls(
            db_pool_min=_as_int(os.getenv("DB_POOL_MIN"), 1),
            db_pool_max=_as_int(os.getenv("DB_POOL_MAX"), 20),
            pin_ttl_seconds=_as_int(os.getenv("PIN_TTL_SECONDS"), 300),
            max_pin_attempts=_as_int(os.getenv("MAX_PIN_ATTEMPTS"), 5),
            pin_lock_seconds=_as_int(os.getenv("PIN_LOCK_SECONDS"), 300),
            face_distance_threshold=float(
                os.getenv("FACE_DISTANCE_THRESHOLD", "0.40")
            ),
        )
