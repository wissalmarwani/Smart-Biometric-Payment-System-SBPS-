#!/usr/bin/env python
# test_verify.py - Test /verify_face endpoint

import base64
import requests
import os

# URL de l'endpoint
url = "http://127.0.0.1:5000/verify_face"

# Dossier des images de test
images_folder = "models/faces"

print("=" * 60)
print("TEST ENDPOINT /verify_face")
print("=" * 60)

# D'abord, vérifier le health endpoint
print("\n[1] Testing /health endpoint...")
try:
    response = requests.get("http://127.0.0.1:5000/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"ERROR: {e}")
    print("Flask server not running? Start it with: python app.py")
    exit(1)

# Lister les utilisateurs
print("\n[2] Listing registered users (/users)...")
try:
    response = requests.get("http://127.0.0.1:5000/users")
    print(f"Status: {response.status_code}")
    print(f"Users: {response.json()}")
except Exception as e:
    print(f"ERROR: {e}")

# Tester chaque image
print("\n[3] Testing /verify_face endpoint with test images...")
if not os.path.exists(images_folder):
    print(f"ERROR: {images_folder} not found!")
    exit(1)

for image_file in sorted(os.listdir(images_folder)):
    if image_file.endswith((".jpg", ".jpeg", ".png")):
        image_path = os.path.join(images_folder, image_file)

        print(f"\n  Testing {image_file}...")

        # Lire et encoder l'image en Base64
        try:
            with open(image_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode("utf-8")
                payload = {
                    "image": f"data:image/jpeg;base64,{img_base64}"
                }

            # Envoyer la requête POST
            response = requests.post(url, json=payload)

            print(f"    Status: {response.status_code}")
            result = response.json()
            print(f"    Success: {result.get('success')}")
            print(f"    Message: {result.get('message')}")

            if result.get("data"):
                data = result["data"]
                print(f"    User ID: {data.get('user_id')}")
                print(f"    Name: {data.get('name')}")
                print(f"    Balance: {data.get('balance')}")
                print(f"    Distance: {data.get('distance', 'N/A')}")

        except Exception as e:
            print(f"    ERROR: {str(e)}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
