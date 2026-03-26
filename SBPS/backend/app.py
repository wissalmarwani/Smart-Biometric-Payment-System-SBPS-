# app.py
from flask import Flask, request, jsonify
from db import create_tables, add_user, find_user_by_phone
from face_recognition import encode_face_from_path, verify_face_with_db

app = Flask(__name__)
create_tables()  # créer les tables si elles n'existent pas


@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    phone = data.get("phone")
    pin = data.get("pin")
    face_image_path = data.get("face_image_path")

    if not all([name, phone, pin, face_image_path]):
        return jsonify({"error": "Tous les champs sont requis"}), 400

    face_encoding = encode_face_from_path(face_image_path)
    if face_encoding is None:
        return jsonify({"error": "Visage non détecté"}), 400

    try:
        add_user(name, phone, pin, face_encoding)
        return jsonify({"message": "Utilisateur enregistré avec succès"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/verify_face", methods=["POST"])
def verify():
    data = request.json
    phone = data.get("phone")
    face_image_path = data.get("face_image_path")

    user = find_user_by_phone(phone)
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    face_encoding = user[4]  # face_encoding
    if verify_face_with_db(face_encoding, face_image_path):
        return jsonify({"message": "Paiement autorisé"})

    return jsonify({"message": "Visage non reconnu"}), 401


if __name__ == "__main__":
    app.run(debug=True)
