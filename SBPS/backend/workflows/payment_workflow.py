from services.user_service import UserNotFoundError


class InvalidAmountError(RuntimeError):
    """Raised when payment amount is invalid."""


class PinVerificationRequiredError(RuntimeError):
    """Raised when payment is attempted without valid PIN verification."""


class PaymentWorkflowService:
    """Facade for PIN verification + payment flow orchestration."""

    def __init__(
        self,
        user_service,
        pin_verification_store,
        max_pin_attempts,
        pin_lock_seconds,
    ):
        self.user_service = user_service
        self.pin_verification_store = pin_verification_store
        self.max_pin_attempts = int(max_pin_attempts)
        self.pin_lock_seconds = int(pin_lock_seconds)

    def verify_pin(self, user_id, provided_pin):
        user = self.user_service.verify_pin_secure(
            user_id=user_id,
            provided_pin=provided_pin,
            max_attempts=self.max_pin_attempts,
            lock_seconds=self.pin_lock_seconds,
        )
        self.pin_verification_store.mark_verified(user_id)
        return user

    def process_payment(self, user_id, amount_raw):
        amount = self._parse_amount(amount_raw)

        user = self.user_service.get_user(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        if not self.pin_verification_store.has_valid_verification(user_id):
            raise PinVerificationRequiredError("PIN verification required")

        payment_result = self.user_service.process_payment_atomic(
            user_id,
            amount,
        )
        self.pin_verification_store.clear(user_id)
        return payment_result

    @staticmethod
    def _parse_amount(amount_raw):
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError) as exc:
            raise InvalidAmountError("Amount must be a number") from exc

        if amount <= 0:
            raise InvalidAmountError("Amount must be greater than 0")

        return amount
