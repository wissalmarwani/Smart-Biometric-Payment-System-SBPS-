#!/usr/bin/env python
import json
import os
from decimal import Decimal, InvalidOperation

import psycopg2
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_JSON = os.path.join(BASE_DIR, "models", "users.json")


def normalize_balance(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid balance value: {value}") from exc


def main():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    if not os.path.exists(USERS_JSON):
        raise FileNotFoundError(f"users.json not found: {USERS_JSON}")

    with open(USERS_JSON, "r", encoding="utf-8") as f:
        users_data = json.load(f)

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cursor:
            for raw_user_id, user in users_data.items():
                user_id = int(raw_user_id)
                name = str(user.get("name", "")).strip()
                face_path = str(user.get("face_path", "")).strip()
                pin = str(user.get("pin", "")).strip()
                balance = normalize_balance(user.get("balance", 0))

                if not name or not face_path or not pin:
                    raise ValueError(
                        f"Invalid user record for user_id={user_id}: "
                        "name/face_path/pin must be provided"
                    )

                cursor.execute(
                    """
                    INSERT INTO users (
                        user_id,
                        name,
                        face_path,
                        balance,
                        pin,
                        is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        face_path = EXCLUDED.face_path,
                        balance = EXCLUDED.balance,
                        pin = EXCLUDED.pin,
                        is_active = TRUE
                    """,
                    (user_id, name, face_path, balance, pin),
                )

        conn.commit()
        print(f"Migration completed: {len(users_data)} users migrated")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
