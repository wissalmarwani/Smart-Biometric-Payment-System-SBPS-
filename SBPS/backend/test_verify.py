#!/usr/bin/env python
# test_verify.py - Test /verify_face endpoint

import base64
import os

import requests

BASE_URL = "http://127.0.0.1:5000"
VERIFY_FACE_URL = f"{BASE_URL}/verify_face"
HEALTH_URL = f"{BASE_URL}/health"
USERS_URL = f"{BASE_URL}/users"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")

# Dossier des images de test
images_folder = "models/faces"

print("=" * 60)
print("TEST ENDPOINT /verify_face")
print("=" * 60)


def print_endpoint_status(label, url, output_label):
    print(f"\n{label}")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"{output_label}: {response.json()}")
        return True
    except Exception as exc:
        print(f"ERROR: {exc}")
        return False


def build_payload(image_path):
    with open(image_path, "rb") as file_handle:
        img_base64 = base64.b64encode(file_handle.read()).decode("utf-8")
    return {"image": f"data:image/jpeg;base64,{img_base64}"}


def test_image(image_file):
    image_path = os.path.join(images_folder, image_file)
    print(f"\n  Testing {image_file}...")

    try:
        payload = build_payload(image_path)
        response = requests.post(VERIFY_FACE_URL, json=payload, timeout=20)
        result = response.json()
    except Exception as exc:
        print(f"    ERROR: {exc}")
        return

    print(f"    Status: {response.status_code}")
    print(f"    Success: {result.get('success')}")
    print(f"    Message: {result.get('message')}")

    data = result.get("data")
    if data:
        print(f"    User ID: {data.get('user_id')}")
        print(f"    Name: {data.get('name')}")
        print(f"    Balance: {data.get('balance')}")
        print(f"    Distance: {data.get('distance', 'N/A')}")


print("\n[1] Testing /health endpoint...")
if not print_endpoint_status("", HEALTH_URL, "Response"):
    print("Flask server not running? Start it with: python app.py")
    raise SystemExit(1)

print("\n[2] Listing registered users (/users)...")
print_endpoint_status("", USERS_URL, "Users")

print("\n[3] Testing /verify_face endpoint with test images...")
if not os.path.exists(images_folder):
    print(f"ERROR: {images_folder} not found!")
    raise SystemExit(1)

for image_file in sorted(os.listdir(images_folder)):
    if image_file.lower().endswith(IMAGE_EXTENSIONS):
        test_image(image_file)

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
