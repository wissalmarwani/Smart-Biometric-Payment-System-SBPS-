import os
from abc import ABC, abstractmethod

from deepface import DeepFace


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
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def resolve(self, relative_path):
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

    def __init__(self, users_provider, path_resolver, strategy):
        self._users_provider = users_provider
        self._path_resolver = path_resolver
        self._strategy = strategy

    def verify_face(self, image_array, distance_threshold=0.40):
        users_data = self._users_provider()
        best_match = None
        best_distance = float("inf")

        for user in users_data:
            face_path = self._path_resolver.resolve(user.get("face_path"))
            if not face_path:
                continue

            try:
                result = self._strategy.compare(image_array, face_path)
            except Exception:
                continue

            distance = result.get("distance", float("inf"))
            if distance < best_distance:
                best_distance = distance
                verified = result.get("verified", False)
                if verified or distance < float(distance_threshold):
                    best_match = {
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

        return best_match
