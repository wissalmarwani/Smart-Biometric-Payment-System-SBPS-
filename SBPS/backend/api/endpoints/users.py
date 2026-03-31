"""Read-only user and health endpoints."""

from flask import request

from api.http import api_error, api_success


def register_user_endpoints(api, factory):
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
        """Return recent transactions; limit is capped by service layer."""
        try:
            service = factory.get_user_service()
            limit = request.args.get("limit", 20)
            transactions = service.list_transactions(limit=limit)
            return api_success(data=transactions, count=len(transactions))
        except Exception as exc:
            return api_error(500, str(exc), data=[], count=0)
