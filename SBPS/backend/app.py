# backend/app.py
from flask import Flask, jsonify


app = Flask(__name__)


@app.route("/api/status")
def status():
    return jsonify({"status": "ready", "camera": True, "db": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)