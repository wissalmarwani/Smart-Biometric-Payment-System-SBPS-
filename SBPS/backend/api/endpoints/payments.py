"""Payment execution endpoints."""

from flask import request

from api.http import api_error, api_success
from services.user_service import (
    InsufficientBalanceError,
    UserNotFoundError,
    UserServiceError,
)
from workflows.payment_workflow import (
    InvalidAmountError,
    PinVerificationRequiredError,
)


def register_payment_endpoints(api, factory):
    @api.route("/pay", methods=["POST"])
    def pay_endpoint():
        """Debit account after PIN validation and return balance."""
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
