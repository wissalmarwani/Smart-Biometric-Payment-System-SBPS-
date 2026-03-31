"""Biometric and PIN verification endpoints."""

from flask import request

from api.http import api_error, api_success, decode_image_data_uri
from services.user_service import (
    InvalidPinError,
    PinLockedError,
    UserNotFoundError,
    UserServiceError,
)


def register_verification_endpoints(api, factory):
    @api.route("/verify_face", methods=["POST"])
    def verify_face_endpoint():
        """Validate face identity and liveness from incoming image payload."""
        try:
            data = request.json
            if not data or "image" not in data:
                return api_error(400, "Missing image data", data=None)

            try:
                image_array = decode_image_data_uri(data["image"])
            except Exception as exc:
                return api_error(
                    400,
                    f"Image decode error: {str(exc)}",
                    data=None,
                )

            threshold = float(
                request.args.get(
                    "threshold",
                    factory.settings.face_distance_threshold,
                )
            )
            face_service = factory.get_face_verification_service()
            user = face_service.verify_face(image_array, threshold)
            liveness_result = getattr(
                face_service,
                "last_liveness_result",
                None,
            )

            if liveness_result and not liveness_result.get("is_live", False):
                return api_error(
                    403,
                    "Liveness check failed (possible spoof)",
                    data=None,
                    liveness=liveness_result,
                )

            if user:
                return api_success(
                    data=user,
                    pin_required=True,
                    liveness=liveness_result,
                    message="User recognized",
                )

            return api_error(200, "Face not recognized", data=None)

        except Exception as exc:
            return api_error(500, f"Server error: {str(exc)}", data=None)

    @api.route("/verify_pin", methods=["POST"])
    def verify_pin_endpoint():
        """Check user PIN and open short-lived payment authorization window."""
        try:
            data = request.json
            if not data:
                return api_error(400, "Missing request data")

            user_id = data.get("user_id")
            pin = str(data.get("pin", "")).strip()

            if not user_id or not pin:
                return api_error(400, "user_id and pin are required")

            workflow = factory.get_payment_workflow_service()
            try:
                user = workflow.verify_pin(user_id=user_id, provided_pin=pin)
            except UserNotFoundError:
                return api_error(404, "User not found")
            except PinLockedError as exc:
                return api_error(
                    423,
                    "Too many failed attempts. Try again later.",
                    retry_after_seconds=exc.retry_after_seconds,
                    locked_until=(
                        exc.locked_until.isoformat()
                        if exc.locked_until
                        else None
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

            return api_success(
                data={
                    "user_id": str(user_id),
                    "name": user.get("name"),
                },
                message="PIN verified",
            )

        except Exception as exc:
            return api_error(500, f"Server error: {str(exc)}")
