from abc import ABC, abstractmethod
from importlib import import_module
from typing import Any, Dict, Optional

import cv2
import numpy as np
from deepface import DeepFace


class LivenessCheckError(RuntimeError):
    """Raised when liveness verification cannot be executed."""


LivenessResult = Dict[str, Any]


class LivenessStrategy(ABC):
    @abstractmethod
    def check(self, image_array) -> LivenessResult:
        """Return dict with keys: is_live, score, reason."""


class DeepFaceAntiSpoofLivenessStrategy(LivenessStrategy):
    """Uses DeepFace built-in anti-spoofing model."""

    def __init__(self, detector_backend="opencv", min_live_score=0.75):
        self.detector_backend = detector_backend
        self.min_live_score = float(min_live_score)

    def check(self, image_array) -> LivenessResult:
        try:
            faces = DeepFace.extract_faces(
                img_path=image_array,
                detector_backend=self.detector_backend,
                enforce_detection=False,
                anti_spoofing=True,
            )
        except Exception as exc:
            raise LivenessCheckError(
                f"DeepFace anti-spoofing error: {exc}"
            ) from exc

        if not faces:
            return self._result(
                is_live=False,
                score=0.0,
                reason="no_face_detected",
            )

        first_face = faces[0]
        is_real = first_face.get("is_real")
        score = first_face.get("antispoof_score")

        if is_real is None:
            if score is None:
                is_real = False
                score = 0.0
            else:
                is_real = float(score) >= self.min_live_score

        return self._result(
            is_live=bool(is_real),
            score=float(score) if score is not None else None,
            reason="ok" if is_real else "possible_spoof",
        )

    @staticmethod
    def _result(is_live: bool, score: Optional[float], reason: str):
        return {
            "is_live": bool(is_live),
            "score": score,
            "reason": reason,
            "source": "deepface",
        }


class TensorFlowLivenessStrategy(LivenessStrategy):
    """Loads a TensorFlow/Keras model for live-vs-spoof classification."""

    def __init__(
        self,
        model_path,
        input_size=224,
        live_class_index=1,
        min_live_score=0.75,
        detector_backend="opencv",
    ):
        if not model_path:
            raise ValueError("model_path is required for TensorFlow liveness")

        self.model_path = model_path
        self.input_size = int(input_size)
        self.live_class_index = int(live_class_index)
        self.min_live_score = float(min_live_score)
        self.detector_backend = detector_backend
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            keras_models = import_module("tensorflow.keras.models")
            load_model = getattr(keras_models, "load_model")
        except Exception as exc:
            raise LivenessCheckError(
                "TensorFlow is not installed. "
                "Install tensorflow to use this strategy."
            ) from exc

        try:
            self._model = load_model(self.model_path)
        except Exception as exc:
            raise LivenessCheckError(
                f"Failed to load liveness model at '{self.model_path}': {exc}"
            ) from exc

        return self._model

    def _extract_face_crop(self, image_array):
        faces = DeepFace.extract_faces(
            img_path=image_array,
            detector_backend=self.detector_backend,
            enforce_detection=False,
            anti_spoofing=False,
        )
        if not faces:
            return None

        face_img = faces[0].get("face")
        if face_img is None:
            return None

        face = np.asarray(face_img)
        if face.dtype != np.float32:
            face = face.astype("float32")

        max_value = float(np.max(face)) if face.size else 0.0
        if max_value > 1.5:
            face = face / 255.0

        resized = cv2.resize(
            face,
            (self.input_size, self.input_size),
            interpolation=cv2.INTER_AREA,
        )
        resized = np.asarray(resized, dtype="float32")
        resized = np.expand_dims(resized, axis=0)

        return resized

    def check(self, image_array) -> LivenessResult:
        model = self._load_model()

        try:
            face_batch = self._extract_face_crop(image_array)
        except Exception as exc:
            raise LivenessCheckError(
                f"Face crop extraction failed: {exc}"
            ) from exc

        if face_batch is None:
            return self._result(
                is_live=False,
                score=0.0,
                reason="no_face_detected",
            )

        try:
            prediction = model.predict(face_batch, verbose=0)
        except Exception as exc:
            raise LivenessCheckError(
                f"Liveness model prediction failed: {exc}"
            ) from exc

        probs = np.asarray(prediction).squeeze()
        if probs.ndim == 0:
            live_score = float(probs)
        elif probs.ndim == 1:
            if probs.shape[0] == 1:
                live_score = float(probs[0])
            else:
                if self.live_class_index >= probs.shape[0]:
                    raise LivenessCheckError(
                        "live_class_index="
                        f"{self.live_class_index} out of range "
                        f"for output size {probs.shape[0]}"
                    )
                live_score = float(probs[self.live_class_index])
        else:
            raise LivenessCheckError(
                f"Unexpected prediction shape: {np.asarray(prediction).shape}"
            )

        is_live = live_score >= self.min_live_score
        return self._result(
            is_live=bool(is_live),
            score=float(live_score),
            reason="ok" if is_live else "possible_spoof",
        )

    @staticmethod
    def _result(is_live: bool, score: Optional[float], reason: str):
        return {
            "is_live": bool(is_live),
            "score": score,
            "reason": reason,
            "source": "tensorflow",
        }


class LivenessService:
    """Facade around a liveness strategy with fail-safe controls."""

    def __init__(self, strategy=None, enabled=True):
        self._strategy = strategy
        self._enabled = bool(enabled)

    def check(self, image_array) -> LivenessResult:
        if not self._enabled or self._strategy is None:
            return {
                "is_live": True,
                "score": None,
                "reason": "disabled",
                "source": "none",
            }

        return self._strategy.check(image_array)
