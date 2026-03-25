from deepface import DeepFace
import numpy as np
import cv2
from deepface.modules.exceptions import FaceNotDetected

print("Chargement du modèle Facenet512...")
# modèle sera utilisé automatiquement par DeepFace
# DeepFace.build_model() reste utile pour le pré-chargement
model = DeepFace.build_model("Facenet512")
print("Modèle prêt ✅")


def get_face_embedding(img):
    """Convertit BGR OpenCV -> embedding 512D"""
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    # Enlever model=model
    try:
        result = DeepFace.represent(
            img_path=rgb_img,
            model_name="Facenet512",
            enforce_detection=True,
            detector_backend="opencv",
        )[0]
    except FaceNotDetected:
        return None

    embedding = np.array(result["embedding"])
    return embedding


def match_face(embedding, db_embeddings, threshold=0.38):
    """Compare encodage avec DB, retourne user_id si match"""
    for user_id, db_emb in db_embeddings.items():
        dist = np.linalg.norm(embedding - db_emb)
        if dist < threshold:
            return user_id, dist
    return None, None
