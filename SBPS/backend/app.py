# backend/app.py
from flask import Flask, request, jsonify, send_from_directory
from deepface import DeepFace
import base64
import os
import time
import numpy as np
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

from db import DBConfigError
from user_service import (
    InsufficientBalanceError,
    UserNotFoundError,
    UserService,
    UserServiceError,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
PIN_VERIFIED = {}
PIN_TTL_SECONDS = 300

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

load_dotenv()


def _get_int_env(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


SERVICE_INIT_ERROR = None
try:
    user_service = UserService(
        min_conn=_get_int_env("DB_POOL_MIN", 1),
        max_conn=_get_int_env("DB_POOL_MAX", 20),
    )
except DBConfigError as exc:
    user_service = None
    SERVICE_INIT_ERROR = str(exc)


def ensure_service_ready():
    if user_service is None:
        message = SERVICE_INIT_ERROR or "Database service is not initialized"
        raise RuntimeError(message)

    return user_service


def mark_pin_verified(user_id):
    """Mark a user as PIN-verified for a short period."""
    PIN_VERIFIED[str(user_id)] = time.time()


def has_valid_pin_verification(user_id):
    """Check whether user PIN was verified and is still valid."""
    verified_at = PIN_VERIFIED.get(str(user_id))
    if not verified_at:
        return False
    if (time.time() - verified_at) > PIN_TTL_SECONDS:
        PIN_VERIFIED.pop(str(user_id), None)
        return False
    return True


def clear_pin_verification(user_id):
    """Remove user PIN-verified state."""
    PIN_VERIFIED.pop(str(user_id), None)


def resolve_face_path(relative_path):
    """Resolve face image path (supports .png, .jpg, .jpeg)."""
    if not relative_path:
        return None

    normalized = os.path.normpath(relative_path)
    candidate = (normalized if os.path.isabs(normalized)
                 else os.path.join(BASE_DIR, normalized))

    if os.path.exists(candidate):
        return candidate

    root, ext = os.path.splitext(candidate)
    for alt_ext in (".png", ".jpg", ".jpeg"):
        alt_candidate = root + alt_ext
        if os.path.exists(alt_candidate):
            return alt_candidate
    return None


def verify_face_from_image(image_array, distance_threshold=0.40):
    """Verify face against all registered users."""
    service = ensure_service_ready()
    users_data = service.list_users()
    best_match = None
    best_distance = float("inf")

    for user in users_data:
        user_id = user.get("user_id")
        face_path = resolve_face_path(user.get("face_path"))
        if not face_path:
            continue

        try:
            result = DeepFace.verify(
                image_array, face_path,
                enforce_detection=False,
                detector_backend="opencv",
                model_name="Facenet512"
            )

            distance = result.get("distance", float("inf"))
            if distance < best_distance:
                best_distance = distance
                verified = result.get("verified", False)
                if verified or distance < distance_threshold:
                    best_match = {
                        "user_id": user_id,
                        "name": user["name"],
                        "balance": user["balance"],
                        "distance": distance,
                        "model": "Facenet512"
                    }
        except Exception:
            continue

    return best_match


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>", methods=["GET"])
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/health", methods=["GET"])
def health_check():
    try:
        service = ensure_service_ready()
        users_count = service.count_users()
        return jsonify({
            "success": True,
            "users_count": users_count,
            "status": "ready"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "users_count": 0,
            "status": "db_error",
            "message": str(e)
        }), 500


@app.route("/users", methods=["GET"])
def list_users():
    try:
        service = ensure_service_ready()
        users = service.list_users()
        users_list = [
            {
                "user_id": user.get("user_id"),
                "name": user.get("name"),
                "balance": user.get("balance"),
            }
            for user in users
        ]
        return jsonify({
            "success": True,
            "data": users_list,
            "count": len(users_list)
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "count": 0,
            "message": str(e)
        }), 500


@app.route("/transactions", methods=["GET"])
def list_transactions():
    try:
        service = ensure_service_ready()
        limit = request.args.get("limit", 20)
        transactions = service.list_transactions(limit=limit)
        return jsonify({
            "success": True,
            "data": transactions,
            "count": len(transactions)
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "count": 0,
            "message": str(e)
        }), 500


@app.route("/verify_face", methods=["POST"])
def verify_face_endpoint():
    """Verify face identity from image data."""
    try:
        data = request.json
        if not data or "image" not in data:
            return jsonify({
                "success": False,
                "data": None,
                "message": "Missing image data"
            }), 400

        image_data_uri = data["image"]
        try:
            if "," in image_data_uri:
                image_data = image_data_uri.split(",")[1]
            else:
                image_data = image_data_uri

            image_bytes = base64.b64decode(image_data)
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            image_array = np.array(image)
        except Exception as e:
            return jsonify({
                "success": False,
                "data": None,
                "message": f"Image decode error: {str(e)}"
            }), 400

        threshold = float(request.args.get("threshold", 0.40))
        user = verify_face_from_image(image_array, threshold)

        if user:
            return jsonify({
                "success": True,
                "data": user,
                "pin_required": True,
                "message": "User recognized"
            }), 200

        return jsonify({
            "success": False,
            "data": None,
            "message": "Face not recognized"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Server error: {str(e)}"
        }), 500


@app.route("/verify_pin", methods=["POST"])
def verify_pin_endpoint():
    """Verify user PIN after face recognition."""
    try:
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "message": "Missing request data"
            }), 400

        user_id = data.get("user_id")
        pin = str(data.get("pin", "")).strip()

        if not user_id or not pin:
            return jsonify({
                "success": False,
                "message": "user_id and pin are required"
            }), 400

        service = ensure_service_ready()

        try:
            is_valid, user = service.verify_pin_plaintext(user_id, pin)
        except UserNotFoundError:
            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404

        stored_pin = str(user.get("pin", "")).strip() if user else ""
        if not stored_pin:
            return jsonify({
                "success": False,
                "message": "PIN not configured for user"
            }), 400

        if not is_valid:
            return jsonify({
                "success": False,
                "message": "Invalid PIN"
            }), 401

        mark_pin_verified(user_id)

        return jsonify({
            "success": True,
            "data": {
                "user_id": str(user_id),
                "name": user.get("name")
            },
            "message": "PIN verified"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500


@app.route("/pay", methods=["POST"])
def pay_endpoint():
    """Process payment after PIN verification."""
    try:
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "message": "Missing request data"
            }), 400

        user_id = data.get("user_id")
        amount_raw = data.get("amount")

        if not user_id or amount_raw is None:
            return jsonify({
                "success": False,
                "message": "user_id and amount are required"
            }), 400

        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "Amount must be a number"
            }), 400

        if amount <= 0:
            return jsonify({
                "success": False,
                "message": "Amount must be greater than 0"
            }), 400

        service = ensure_service_ready()

        user = service.get_user(user_id)
        if not user:
            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404

        if not has_valid_pin_verification(user_id):
            return jsonify({
                "success": False,
                "message": "PIN verification required"
            }), 401

        try:
            payment_result = service.process_payment_atomic(user_id, amount)
        except InsufficientBalanceError as exc:
            return jsonify({
                "success": False,
                "data": {
                    "user_id": str(user_id),
                    "name": user.get("name"),
                    "current_balance": round(float(exc.current_balance), 2),
                    "amount": round(amount, 2)
                },
                "message": "Non: solde insuffisant"
            }), 400
        except UserNotFoundError:
            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404
        except UserServiceError as exc:
            return jsonify({
                "success": False,
                "message": str(exc)
            }), 400

        clear_pin_verification(user_id)

        return jsonify({
            "success": True,
            "data": {
                "user_id": str(user_id),
                "name": payment_result.get("name"),
                "amount": round(
                    float(payment_result.get("amount", amount)), 2
                ),
                "new_balance": round(
                    float(payment_result.get("new_balance", 0)), 2
                )
            },
            "message": "Paiement effectué"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
