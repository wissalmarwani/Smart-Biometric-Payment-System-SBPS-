"""Legacy face embedding helpers used by standalone scripts."""

import json
from typing import Optional

import cv2
import numpy as np
from deepface import DeepFace
from deepface.modules.exceptions import FaceNotDetected

MODEL_NAME = "Facenet512"
DETECTOR_BACKEND = "opencv"


def get_face_embedding(img: np.ndarray) -> Optional[np.ndarray]:
    """Convert OpenCV BGR image into a Facenet embedding vector."""
    if img is None:
        return None

    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    try:
        result = DeepFace.represent(
            img_path=rgb_img,
            model_name=MODEL_NAME,
            enforce_detection=True,
            detector_backend=DETECTOR_BACKEND,
        )[0]
    except FaceNotDetected:
        return None

    embedding = np.array(result["embedding"])
    return embedding


def encode_face_from_path(image_path: str) -> Optional[str]:
    """Encode face from image path for JSON storage."""
    img = cv2.imread(image_path)
    embedding = get_face_embedding(img)
    if embedding is None:
        return None

    return json.dumps(embedding.tolist())


def verify_face_with_db(
    known_encoding_json: str,
    image_path: str,
    threshold: float = 0.38,
) -> bool:
    """
    Compare an image face against a stored embedding vector.

    Uses euclidean distance, so practical thresholds are usually lower.
    """
    known_embedding = np.array(json.loads(known_encoding_json))
    img = cv2.imread(image_path)
    embedding = get_face_embedding(img)
    if embedding is None:
        return False

    dist = np.linalg.norm(embedding - known_embedding)
    return dist < threshold
