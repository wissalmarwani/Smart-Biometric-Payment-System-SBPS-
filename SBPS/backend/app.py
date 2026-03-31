# backend/app.py
from flask import Flask, send_from_directory
import os
from dotenv import load_dotenv

from api.routes import create_api_blueprint
from application_factory import ApplicationFactory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

load_dotenv()

factory = ApplicationFactory(base_dir=BASE_DIR)

app.register_blueprint(create_api_blueprint(factory))


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>", methods=["GET"])
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
