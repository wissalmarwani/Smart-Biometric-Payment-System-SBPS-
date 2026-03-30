import os
from dataclasses import dataclass


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _as_bool(value, default=False):
    if value is None:
        return bool(default)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return bool(default)


@dataclass(frozen=True)
class AppSettings:
    db_pool_min: int
    db_pool_max: int
    pin_ttl_seconds: int
    max_pin_attempts: int
    pin_lock_seconds: int
    face_distance_threshold: float
    liveness_enabled: bool
    liveness_strategy: str
    liveness_model_path: str
    liveness_min_score: float
    liveness_input_size: int
    liveness_live_class_index: int

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
            liveness_enabled=_as_bool(
                os.getenv("LIVENESS_ENABLED", "true"),
                default=True,
            ),
            liveness_strategy=str(
                os.getenv("LIVENESS_STRATEGY", "deepface")
            ).strip().lower(),
            liveness_model_path=str(
                os.getenv("LIVENESS_MODEL_PATH", "")
            ).strip(),
            liveness_min_score=float(
                os.getenv("LIVENESS_MIN_SCORE", "0.75")
            ),
            liveness_input_size=_as_int(
                os.getenv("LIVENESS_INPUT_SIZE", 224),
                224,
            ),
            liveness_live_class_index=_as_int(
                os.getenv("LIVENESS_LIVE_CLASS_INDEX", 1),
                1,
            ),
        )
