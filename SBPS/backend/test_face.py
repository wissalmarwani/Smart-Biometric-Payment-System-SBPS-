import cv2
from ai.face_recognition import get_face_embedding


def capture_warm_frame(camera_id=0, warmup_reads=10):
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        return None

    try:
        for _ in range(warmup_reads):
            ok, frame = cap.read()
            if ok:
                return frame
        return None
    finally:
        cap.release()


def main():
    frame = capture_warm_frame()
    if frame is None:
        print("Impossible de capturer l'image")
        return

    embedding = get_face_embedding(frame)
    if embedding is None:
        print("Aucun visage détecté. Regardez la caméra et réessayez.")
        return

    print("Encodage 512D généré :", embedding.shape)


if __name__ == "__main__":
    main()
