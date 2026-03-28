# backend/app.py
from flask import Flask, request, jsonify, send_from_directory
from deepface import DeepFace
import base64
import os
import json
import time
import numpy as np
from PIL import Image
from io import BytesIO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
USERS_DB = os.path.join(BASE_DIR, "models", "users.json")
PIN_VERIFIED = {}
PIN_TTL_SECONDS = 300

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")


def load_users_data():
    """Load users from JSON database."""
    if os.path.exists(USERS_DB):
        with open(USERS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users_data(users_data):
    """Persist users JSON database."""
    with open(USERS_DB, "w", encoding="utf-8") as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)


def get_user(users_data, user_id):
    """Get a user by id from JSON map."""
    return users_data.get(str(user_id))


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
    users_data = load_users_data()
    best_match = None
    best_distance = float("inf")

    for user_id, user in users_data.items():
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
    users = load_users_data()
    return jsonify({
        "success": True,
        "users_count": len(users),
        "status": "ready"
    }), 200


@app.route("/users", methods=["GET"])
def list_users():
    users = load_users_data()
    users_list = [
        {"user_id": uid, "name": user.get("name"),
         "balance": user.get("balance")}
        for uid, user in users.items()
    ]
    return jsonify({
        "success": True,
        "data": users_list,
        "count": len(users_list)
    }), 200


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

        users_data = load_users_data()
        user = get_user(users_data, user_id)
        if not user:
            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404

        stored_pin = str(user.get("pin", "")).strip()
        if not stored_pin:
            return jsonify({
                "success": False,
                "message": "PIN not configured for user"
            }), 400

        if pin != stored_pin:
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

        users_data = load_users_data()
        user = get_user(users_data, user_id)
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

        balance = float(user.get("balance", 0))
        if balance < amount:
            return jsonify({
                "success": False,
                "data": {
                    "user_id": str(user_id),
                    "name": user.get("name"),
                    "current_balance": round(balance, 2),
                    "amount": round(amount, 2)
                },
                "message": "Non: solde insuffisant"
            }), 400

        new_balance = round(balance - amount, 2)
        user["balance"] = new_balance
        save_users_data(users_data)
        clear_pin_verification(user_id)

        return jsonify({
            "success": True,
            "data": {
                "user_id": str(user_id),
                "name": user.get("name"),
                "amount": round(amount, 2),
                "new_balance": new_balance
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
