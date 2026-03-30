# backend/app.py
from flask import Flask, request, jsonify, send_from_directory
import base64
import os
import numpy as np
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

from application_factory import ApplicationFactory
from user_service import (
    InsufficientBalanceError,
    InvalidPinError,
    PinLockedError,
    UserNotFoundError,
    UserServiceError,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

load_dotenv()

factory = ApplicationFactory(base_dir=BASE_DIR)


def ensure_service_ready():
    return factory.get_user_service()


def get_face_verification_service():
    return factory.get_face_verification_service()


def get_pin_verification_store():
    return factory.get_pin_verification_store()


def api_response(success, status_code, **payload):
    body = {"success": success}
    body.update(payload)
    return jsonify(body), status_code


def api_success(status_code=200, **payload):
    return api_response(True, status_code, **payload)


def api_error(status_code, message, **payload):
    return api_response(False, status_code, message=message, **payload)


def decode_image_data_uri(image_data_uri):
    image_data = (
        image_data_uri.split(",", 1)[1]
        if "," in image_data_uri
        else image_data_uri
    )
    image_bytes = base64.b64decode(image_data)
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    return np.array(image)


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
        return api_success(users_count=users_count, status="ready")
    except Exception as e:
        return api_error(
            500,
            str(e),
            users_count=0,
            status="db_error",
        )


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
        return api_success(data=users_list, count=len(users_list))
    except Exception as e:
        return api_error(500, str(e), data=[], count=0)


@app.route("/transactions", methods=["GET"])
def list_transactions():
    try:
        service = ensure_service_ready()
        limit = request.args.get("limit", 20)
        transactions = service.list_transactions(limit=limit)
        return api_success(data=transactions, count=len(transactions))
    except Exception as e:
        return api_error(500, str(e), data=[], count=0)


@app.route("/verify_face", methods=["POST"])
def verify_face_endpoint():
    """Verify face identity from image data."""
    try:
        data = request.json
        if not data or "image" not in data:
            return api_error(400, "Missing image data", data=None)

        image_data_uri = data["image"]
        try:
            image_array = decode_image_data_uri(image_data_uri)
        except Exception as e:
            return api_error(400, f"Image decode error: {str(e)}", data=None)

        threshold = float(
            request.args.get(
                "threshold",
                factory.settings.face_distance_threshold,
            )
        )
        face_service = get_face_verification_service()
        user = face_service.verify_face(image_array, threshold)

        if user:
            return api_success(
                data=user,
                pin_required=True,
                message="User recognized",
            )

        return api_error(200, "Face not recognized", data=None)

    except Exception as e:
        return api_error(500, f"Server error: {str(e)}", data=None)


@app.route("/verify_pin", methods=["POST"])
def verify_pin_endpoint():
    """Verify user PIN after face recognition."""
    try:
        data = request.json
        if not data:
            return api_error(400, "Missing request data")

        user_id = data.get("user_id")
        pin = str(data.get("pin", "")).strip()

        if not user_id or not pin:
            return api_error(400, "user_id and pin are required")

        service = ensure_service_ready()
        max_attempts = factory.settings.max_pin_attempts
        lock_seconds = factory.settings.pin_lock_seconds

        try:
            user = service.verify_pin_secure(
                user_id=user_id,
                provided_pin=pin,
                max_attempts=max_attempts,
                lock_seconds=lock_seconds,
            )
        except UserNotFoundError:
            return api_error(404, "User not found")
        except PinLockedError as exc:
            return api_error(
                423,
                "Too many failed attempts. Try again later.",
                retry_after_seconds=exc.retry_after_seconds,
                locked_until=(
                    exc.locked_until.isoformat() if exc.locked_until else None
                ),
            )
        except InvalidPinError as exc:
            remaining = exc.remaining_attempts
            message = "Invalid PIN"
            if remaining is not None:
                message = f"Invalid PIN. Remaining attempts: {remaining}"
            return api_error(401, message, remaining_attempts=remaining)
        except UserServiceError as exc:
            return api_error(400, str(exc))

        get_pin_verification_store().mark_verified(user_id)

        return api_success(
            data={
                "user_id": str(user_id),
                "name": user.get("name"),
            },
            message="PIN verified",
        )

    except Exception as e:
        return api_error(500, f"Server error: {str(e)}")


@app.route("/pay", methods=["POST"])
def pay_endpoint():
    """Process payment after PIN verification."""
    try:
        data = request.json
        if not data:
            return api_error(400, "Missing request data")

        user_id = data.get("user_id")
        amount_raw = data.get("amount")

        if not user_id or amount_raw is None:
            return api_error(400, "user_id and amount are required")

        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            return api_error(400, "Amount must be a number")

        if amount <= 0:
            return api_error(400, "Amount must be greater than 0")

        service = ensure_service_ready()

        user = service.get_user(user_id)
        if not user:
            return api_error(404, "User not found")

        if not get_pin_verification_store().has_valid_verification(user_id):
            return api_error(401, "PIN verification required")

        try:
            payment_result = service.process_payment_atomic(user_id, amount)
        except InsufficientBalanceError as exc:
            return api_error(
                400,
                "Non: solde insuffisant",
                data={
                    "user_id": str(user_id),
                    "name": user.get("name"),
                    "current_balance": round(float(exc.current_balance), 2),
                    "amount": round(amount, 2),
                },
            )
        except UserNotFoundError:
            return api_error(404, "User not found")
        except UserServiceError as exc:
            return api_error(400, str(exc))

        get_pin_verification_store().clear(user_id)

        return api_success(
            data={
                "user_id": str(user_id),
                "name": payment_result.get("name"),
                "amount": round(
                    float(payment_result.get("amount", amount)), 2
                ),
                "new_balance": round(
                    float(payment_result.get("new_balance", 0)), 2
                ),
            },
            message="Paiement effectué",
        )

    except Exception as e:
        return api_error(500, f"Server error: {str(e)}")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
