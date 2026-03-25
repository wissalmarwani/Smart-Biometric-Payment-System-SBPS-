import cv2
from face_recognition import get_face_embedding

cap = cv2.VideoCapture(0)

# Warm up camera to improve chance of getting a sharp frame.
ret = False
frame = None
for _ in range(10):
    ret, frame = cap.read()
    if ret:
        break

cap.release()

if ret:
    embedding = get_face_embedding(frame)
    if embedding is None:
        print("Aucun visage détecté. Regardez la caméra et réessayez.")
    else:
        print("Encodage 512D généré :", embedding.shape)
else:
    print("Impossible de capturer l'image")
