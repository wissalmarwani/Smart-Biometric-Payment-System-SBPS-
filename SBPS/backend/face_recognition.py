# face_recognition.py
import json

import cv2
import numpy as np
from deepface import DeepFace
from deepface.modules.exceptions import FaceNotDetected

print("Chargement du modele Facenet512...")
model = DeepFace.build_model("Facenet512")
print("Modele pret")


def get_face_embedding(img):
    """Convertit BGR OpenCV -> embedding 512D"""
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    try:
        result = DeepFace.represent(
            img_path=rgb_img,  # img_path accepte np.ndarray
            model_name="Facenet512",
            enforce_detection=True,
            detector_backend="opencv",
        )[0]
    except FaceNotDetected:
        return None

    embedding = np.array(result["embedding"])
    return embedding


def encode_face_from_path(image_path):
    """Encode un visage depuis un fichier image pour stockage en DB (JSON)"""
    img = cv2.imread(image_path)
    embedding = get_face_embedding(img)
    if embedding is None:
        return None

    return json.dumps(embedding.tolist())  # serialisation pour DB


def verify_face_with_db(known_encoding_json, image_path, threshold=0.38):
    """
    Verifie si le visage correspond au vecteur stocke.
    threshold plus petit car on utilise distance euclidienne.
    """
    known_embedding = np.array(json.loads(known_encoding_json))
    img = cv2.imread(image_path)
    embedding = get_face_embedding(img)
    if embedding is None:
        return False

    dist = np.linalg.norm(embedding - known_embedding)
    return dist < threshold
