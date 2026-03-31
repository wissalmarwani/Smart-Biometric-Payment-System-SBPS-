from db import DBConfigError
from ai.anti_spoofing import (
    DeepFaceAntiSpoofLivenessStrategy,
    LivenessService,
    TensorFlowLivenessStrategy,
)
from ai.face_verification import (
    DeepFaceVerificationStrategy,
    FacePathResolver,
    FaceVerificationService,
)
from security.pin_verification_store import PinVerificationStore
from settings import AppSettings
from services.user_service import UserService
from workflows.payment_workflow import PaymentWorkflowService


class ApplicationFactory:
    """Builds and wires app dependencies (Factory pattern)."""

    def __init__(self, base_dir, settings=None):
        self.base_dir = base_dir
        self.settings = settings or AppSettings.from_env()
        self._user_service = None
        self._service_init_error = None
        self._face_service = None
        self._payment_workflow_service = None
        self._pin_store = PinVerificationStore(
            ttl_seconds=self.settings.pin_ttl_seconds
        )

    def get_user_service(self):
        if self._user_service is not None:
            return self._user_service

        if self._service_init_error is not None:
            raise RuntimeError(self._service_init_error)

        try:
            self._user_service = UserService(
                min_conn=self.settings.db_pool_min,
                max_conn=self.settings.db_pool_max,
            )
        except DBConfigError as exc:
            self._service_init_error = str(exc)
            raise RuntimeError(self._service_init_error) from exc

        return self._user_service

    def get_face_verification_service(self):
        if self._face_service is not None:
            return self._face_service

        service = self.get_user_service()
        path_resolver = FacePathResolver(base_dir=self.base_dir)
        strategy = DeepFaceVerificationStrategy(
            model_name="Facenet512",
            detector_backend="opencv",
        )
        liveness_service = self._build_liveness_service()
        self._face_service = FaceVerificationService(
            users_provider=service.list_users,
            path_resolver=path_resolver,
            strategy=strategy,
            liveness_service=liveness_service,
        )
        return self._face_service

    def get_pin_verification_store(self):
        return self._pin_store

    def get_payment_workflow_service(self):
        if self._payment_workflow_service is not None:
            return self._payment_workflow_service

        self._payment_workflow_service = PaymentWorkflowService(
            user_service=self.get_user_service(),
            pin_verification_store=self.get_pin_verification_store(),
            max_pin_attempts=self.settings.max_pin_attempts,
            pin_lock_seconds=self.settings.pin_lock_seconds,
        )
        return self._payment_workflow_service

    def _build_liveness_service(self):
        if not self.settings.liveness_enabled:
            return LivenessService(enabled=False)

        strategy_name = self.settings.liveness_strategy

        if strategy_name == "tensorflow":
            strategy = TensorFlowLivenessStrategy(
                model_path=self.settings.liveness_model_path,
                input_size=self.settings.liveness_input_size,
                live_class_index=self.settings.liveness_live_class_index,
                min_live_score=self.settings.liveness_min_score,
                detector_backend="opencv",
            )
            return LivenessService(strategy=strategy, enabled=True)

        strategy = DeepFaceAntiSpoofLivenessStrategy(
            detector_backend="opencv",
            min_live_score=self.settings.liveness_min_score,
        )
        return LivenessService(strategy=strategy, enabled=True)
