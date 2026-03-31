from flask import Blueprint, request

from api.http import api_error, api_success, decode_image_data_uri
from user_service import (
    InsufficientBalanceError,
    InvalidPinError,
    PinLockedError,
    UserNotFoundError,
    UserServiceError,
)
from workflows.payment_workflow import (
    InvalidAmountError,
    PinVerificationRequiredError,
)


def create_api_blueprint(factory):
    api = Blueprint("api", __name__)

    @api.route("/health", methods=["GET"])
    def health_check():
        try:
            service = factory.get_user_service()
            users_count = service.count_users()
            return api_success(users_count=users_count, status="ready")
        except Exception as exc:
            return api_error(
                500,
                str(exc),
                users_count=0,
                status="db_error",
            )

    @api.route("/users", methods=["GET"])
    def list_users():
        try:
            service = factory.get_user_service()
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
        except Exception as exc:
            return api_error(500, str(exc), data=[], count=0)

    @api.route("/transactions", methods=["GET"])
    def list_transactions():
        try:
            service = factory.get_user_service()
            limit = request.args.get("limit", 20)
            transactions = service.list_transactions(limit=limit)
            return api_success(data=transactions, count=len(transactions))
        except Exception as exc:
            return api_error(500, str(exc), data=[], count=0)

    @api.route("/verify_face", methods=["POST"])
    def verify_face_endpoint():
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

    @api.route("/pay", methods=["POST"])
    def pay_endpoint():
        try:
            data = request.json
            if not data:
                return api_error(400, "Missing request data")

            user_id = data.get("user_id")
            amount_raw = data.get("amount")

            if not user_id or amount_raw is None:
                return api_error(400, "user_id and amount are required")

            workflow = factory.get_payment_workflow_service()
            try:
                payment_result = workflow.process_payment(
                    user_id=user_id,
                    amount_raw=amount_raw,
                )
            except InvalidAmountError as exc:
                return api_error(400, str(exc))
            except UserNotFoundError:
                return api_error(404, "User not found")
            except PinVerificationRequiredError as exc:
                return api_error(401, str(exc))
            except InsufficientBalanceError as exc:
                return api_error(
                    400,
                    "Non: solde insuffisant",
                    data={
                        "user_id": str(user_id),
                        "current_balance": round(
                            float(exc.current_balance),
                            2,
                        ),
                        "amount": round(float(amount_raw), 2),
                    },
                )
            except UserServiceError as exc:
                return api_error(400, str(exc))

            return api_success(
                data={
                    "user_id": str(user_id),
                    "name": payment_result.get("name"),
                    "amount": round(float(payment_result.get("amount", 0)), 2),
                    "new_balance": round(
                        float(payment_result.get("new_balance", 0)),
                        2,
                    ),
                },
                message="Paiement effectué",
            )

        except Exception as exc:
            return api_error(500, f"Server error: {str(exc)}")

    return api
