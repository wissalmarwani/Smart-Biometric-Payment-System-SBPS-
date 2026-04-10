"""User and admin endpoints."""

import hmac
import os
import secrets
import time
from pathlib import Path

from flask import request
from werkzeug.utils import secure_filename

from api.http import api_error, api_success
from services.user_service import UserNotFoundError, UserServiceError


_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
_ADMIN_PASSWORD = (
    os.getenv("ADMIN_PASSWORD", "admin1234").strip() or "admin1234"
)
_ADMIN_TOKEN_TTL_SECONDS = int(os.getenv("ADMIN_TOKEN_TTL_SECONDS", "3600"))
_ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_ADMIN_TOKENS = {}


def _cleanup_expired_tokens(now_epoch=None):
    now = now_epoch if now_epoch is not None else time.time()
    expired = [
        token
        for token, expiry in _ADMIN_TOKENS.items()
        if expiry <= now
    ]
    for token in expired:
        _ADMIN_TOKENS.pop(token, None)


def _issue_admin_token():
    token = secrets.token_urlsafe(32)
    expiry = time.time() + _ADMIN_TOKEN_TTL_SECONDS
    _ADMIN_TOKENS[token] = expiry
    return token, _ADMIN_TOKEN_TTL_SECONDS


def _extract_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header.split(" ", 1)[1].strip()


def _is_admin_authorized():
    _cleanup_expired_tokens()
    token = _extract_bearer_token()
    if not token:
        return False
    expiry = _ADMIN_TOKENS.get(token)
    if not expiry:
        return False
    if expiry <= time.time():
        _ADMIN_TOKENS.pop(token, None)
        return False
    return True


def _require_admin():
    if not _is_admin_authorized():
        return api_error(401, "Admin authentication required")
    return None


def _faces_dir(factory):
    faces_path = Path(factory.base_dir) / "models" / "faces"
    faces_path.mkdir(parents=True, exist_ok=True)
    return faces_path


def _save_uploaded_image(file_storage, faces_dir):
    if not file_storage or not file_storage.filename:
        raise UserServiceError("image file is required")

    safe_name = secure_filename(file_storage.filename)
    extension = Path(safe_name).suffix.lower()
    if extension not in _ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_IMAGE_EXTENSIONS))
        raise UserServiceError(
            f"unsupported image extension; allowed: {allowed}"
        )

    unique_name = (
        f"user_{int(time.time() * 1000)}_"
        f"{secrets.token_hex(4)}{extension}"
    )
    destination = faces_dir / unique_name
    file_storage.save(destination)
    return f"models/faces/{unique_name}"


def register_user_endpoints(api, factory):
    @api.route("/admin/login", methods=["POST"])
    def admin_login():
        """Authenticate admin and return a bearer token."""
        try:
            data = request.json or {}
            username = str(data.get("username", "")).strip()
            password = str(data.get("password", "")).strip()

            username_ok = hmac.compare_digest(username, _ADMIN_USERNAME)
            password_ok = hmac.compare_digest(password, _ADMIN_PASSWORD)
            if not (username_ok and password_ok):
                return api_error(401, "Invalid admin credentials")

            token, expires_in = _issue_admin_token()
            return api_success(
                data={"token": token, "expires_in": expires_in},
                message="Admin login successful",
            )
        except Exception as exc:
            return api_error(500, str(exc))

    @api.route("/admin/logout", methods=["POST"])
    def admin_logout():
        """Invalidate current admin token."""
        token = _extract_bearer_token()
        if token:
            _ADMIN_TOKENS.pop(token, None)
        return api_success(message="Admin logout successful")

    @api.route("/health", methods=["GET"])
    def health_check():
        """Simple readiness probe backed by user service connectivity."""
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
        """Return active users with public profile fields."""
        unauthorized = _require_admin()
        if unauthorized:
            return unauthorized

        try:
            service = factory.get_user_service()
            users = service.list_users()
            users_list = [
                {
                    "user_id": user.get("user_id"),
                    "name": user.get("name"),
                    "balance": user.get("balance"),
                    "face_path": user.get("face_path"),
                }
                for user in users
            ]
            return api_success(data=users_list, count=len(users_list))
        except Exception as exc:
            return api_error(500, str(exc), data=[], count=0)

    @api.route("/users", methods=["POST"])
    def create_user():
        """Create a new active user for admin management pages."""
        unauthorized = _require_admin()
        if unauthorized:
            return unauthorized

        try:
            data = (
                request.form.to_dict()
                if request.form
                else (request.json or {})
            )
            service = factory.get_user_service()

            face_path = data.get("face_path")
            file_storage = request.files.get("face_file")
            if file_storage:
                face_path = _save_uploaded_image(
                    file_storage=file_storage,
                    faces_dir=_faces_dir(factory),
                )

            created = service.create_user(
                user_id=data.get("user_id"),
                name=data.get("name"),
                face_path=face_path,
                pin=data.get("pin"),
                balance=data.get("balance", 0),
            )
            return api_success(
                status_code=201,
                data=created,
                message="User created",
            )
        except UserServiceError as exc:
            return api_error(400, str(exc))
        except Exception as exc:
            return api_error(500, str(exc))

    @api.route("/users/<user_id>", methods=["DELETE"])
    def delete_user(user_id):
        """Soft delete active user by user_id."""
        unauthorized = _require_admin()
        if unauthorized:
            return unauthorized

        try:
            service = factory.get_user_service()
            service.delete_user(user_id)
            return api_success(message="User deleted", user_id=str(user_id))
        except UserNotFoundError:
            return api_error(404, "User not found")
        except UserServiceError as exc:
            return api_error(400, str(exc))
        except Exception as exc:
            return api_error(500, str(exc))

    @api.route("/users/<user_id>/face_path", methods=["PUT"])
    def update_user_face_path(user_id):
        """Update user picture path used by face matching system."""
        unauthorized = _require_admin()
        if unauthorized:
            return unauthorized

        try:
            data = (
                request.form.to_dict()
                if request.form
                else (request.json or {})
            )
            service = factory.get_user_service()

            face_path = data.get("face_path")
            file_storage = request.files.get("face_file")
            if file_storage:
                face_path = _save_uploaded_image(
                    file_storage=file_storage,
                    faces_dir=_faces_dir(factory),
                )

            updated = service.update_user_face_path(
                user_id=user_id,
                face_path=face_path,
            )
            return api_success(data=updated, message="User picture updated")
        except UserNotFoundError:
            return api_error(404, "User not found")
        except UserServiceError as exc:
            return api_error(400, str(exc))
        except Exception as exc:
            return api_error(500, str(exc))

    @api.route("/transactions", methods=["GET"])
    def list_transactions():
        """Return recent transactions; limit is capped by service layer."""
        unauthorized = _require_admin()
        if unauthorized:
            return unauthorized

        try:
            service = factory.get_user_service()
            limit = request.args.get("limit", 20)
            transactions = service.list_transactions(limit=limit)
            return api_success(data=transactions, count=len(transactions))
        except Exception as exc:
            return api_error(500, str(exc), data=[], count=0)
