import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

from deepface import DeepFace


VerificationResult = Dict[str, Any]
UserRecord = Dict[str, Any]


class FaceVerificationStrategy(ABC):
    @abstractmethod
    def compare(self, probe_image_array, candidate_face_path):
        """Compare probe image with candidate face image."""


class DeepFaceVerificationStrategy(FaceVerificationStrategy):
    def __init__(self, model_name="Facenet512", detector_backend="opencv"):
        self.model_name = model_name
        self.detector_backend = detector_backend

    def compare(self, probe_image_array, candidate_face_path):
        return DeepFace.verify(
            probe_image_array,
            candidate_face_path,
            enforce_detection=False,
            detector_backend=self.detector_backend,
            model_name=self.model_name,
        )


class FacePathResolver:
    """Resolve relative face image paths from storage to existing files."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def resolve(self, relative_path: Optional[str]) -> Optional[str]:
        if not relative_path:
            return None

        normalized = os.path.normpath(relative_path)
        candidate = (
            normalized
            if os.path.isabs(normalized)
            else os.path.join(self.base_dir, normalized)
        )

        if os.path.exists(candidate):
            return candidate

        root, _ = os.path.splitext(candidate)
        for alt_ext in (".png", ".jpg", ".jpeg"):
            alt_candidate = root + alt_ext
            if os.path.exists(alt_candidate):
                return alt_candidate

        return None


class FaceVerificationService:
    """Facade over strategy and user source for face verification."""

    def __init__(
        self,
        users_provider: Callable[[], list],
        path_resolver: FacePathResolver,
        strategy: FaceVerificationStrategy,
        liveness_service=None,
    ):
        self._users_provider = users_provider
        self._path_resolver = path_resolver
        self._strategy = strategy
        self._liveness_service = liveness_service
        self._last_liveness_result = None

    @property
    def last_liveness_result(self) -> Optional[VerificationResult]:
        return self._last_liveness_result

    def verify_face(
        self,
        image_array,
        distance_threshold: float = 0.40,
    ) -> Optional[VerificationResult]:
        """Return best matching user payload or None if no valid match."""
        if not self._run_liveness_check(image_array):
            return None

        users_data = self._users_provider()
        best_match = None
        best_distance = float("inf")

        for user in users_data:
            candidate = self._try_user_match(
                image_array=image_array,
                user=user,
                distance_threshold=distance_threshold,
            )
            if candidate is None:
                continue

            if candidate.get("distance", float("inf")) < best_distance:
                best_distance = float(candidate["distance"])
                best_match = candidate

        return best_match

    def _run_liveness_check(self, image_array) -> bool:
        if self._liveness_service is not None:
            try:
                self._last_liveness_result = self._liveness_service.check(
                    image_array
                )
            except Exception as exc:
                self._last_liveness_result = {
                    "is_live": False,
                    "score": None,
                    "reason": f"liveness_error: {exc}",
                    "source": "liveness_service",
                }

            return bool(self._last_liveness_result.get("is_live", False))

        self._last_liveness_result = {
            "is_live": True,
            "score": None,
            "reason": "not_configured",
            "source": "none",
        }
        return True

    def _try_user_match(
        self,
        image_array,
        user: UserRecord,
        distance_threshold: float,
    ) -> Optional[VerificationResult]:
        face_path = self._path_resolver.resolve(user.get("face_path"))
        if not face_path:
            return None

        try:
            result = self._strategy.compare(image_array, face_path)
        except Exception:
            return None

        distance = float(result.get("distance", float("inf")))
        verified = bool(result.get("verified", False))
        if not verified and distance >= float(distance_threshold):
            return None

        return {
            "user_id": user.get("user_id"),
            "name": user.get("name"),
            "balance": user.get("balance"),
            "distance": distance,
            "model": getattr(
                self._strategy,
                "model_name",
                "unknown",
            ),
        }
