from db import DBConfigError
from face_verification import (
    DeepFaceVerificationStrategy,
    FacePathResolver,
    FaceVerificationService,
)
from pin_verification_store import PinVerificationStore
from settings import AppSettings
from user_service import UserService


class ApplicationFactory:
    """Builds and wires app dependencies (Factory pattern)."""

    def __init__(self, base_dir, settings=None):
        self.base_dir = base_dir
        self.settings = settings or AppSettings.from_env()
        self._user_service = None
        self._service_init_error = None
        self._face_service = None
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
        self._face_service = FaceVerificationService(
            users_provider=service.list_users,
            path_resolver=path_resolver,
            strategy=strategy,
        )
        return self._face_service

    def get_pin_verification_store(self):
        return self._pin_store
