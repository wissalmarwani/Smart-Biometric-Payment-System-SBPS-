import base64
from io import BytesIO

import numpy as np
from flask import jsonify
from PIL import Image


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
