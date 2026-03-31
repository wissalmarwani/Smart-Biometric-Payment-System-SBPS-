"""API blueprint composition.

This module keeps route registration wiring in one place while
endpoint handlers live in focused feature modules.
"""

from flask import Blueprint

from api.endpoints.payments import register_payment_endpoints
from api.endpoints.users import register_user_endpoints
from api.endpoints.verification import register_verification_endpoints


def create_api_blueprint(factory):
    """Create and register all HTTP endpoints on a shared blueprint."""
    api = Blueprint("api", __name__)

    register_user_endpoints(api, factory)
    register_verification_endpoints(api, factory)
    register_payment_endpoints(api, factory)

    return api
