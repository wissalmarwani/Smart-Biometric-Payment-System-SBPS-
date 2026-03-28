# backend/camera.py
import cv2
import base64
from io import BytesIO
from PIL import Image


class CameraCapture:
    """Camera capture and frame encoding."""

    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.cap = None

    def open(self):
        """Open camera and set resolution."""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                raise RuntimeError("Cannot open camera")
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            return True
        except Exception as e:
            print(f"Camera error: {e}")
            return False

    def capture_frame(self):
        """Capture single frame from camera."""
        if self.cap is None or not self.cap.isOpened():
            return None

        try:
            ret, frame = self.cap.read()
            return frame if ret else None
        except Exception as e:
            print(f"Capture error: {e}")
            return None

    def capture_frame_base64(self, format="jpeg"):
        """Capture frame and return as base64 data URI."""
        frame = self.capture_frame()
        if frame is None:
            return None

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)

            buffer = BytesIO()
            if format.lower() == "png":
                pil_image.save(buffer, format="PNG")
                mime_type = "image/png"
            else:
                pil_image.save(buffer, format="JPEG", quality=95)
                mime_type = "image/jpeg"

            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode("utf-8")
            return f"data:{mime_type};base64,{img_base64}"

        except Exception as e:
            print(f"Encoding error: {e}")
            return None

    def close(self):
        """Release camera."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
