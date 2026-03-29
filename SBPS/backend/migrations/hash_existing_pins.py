#!/usr/bin/env python
import os

import bcrypt
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, pin
                FROM users
                WHERE pin IS NOT NULL
                  AND pin <> ''
                  AND (pin_hash IS NULL OR pin_hash = '')
                ORDER BY user_id
                """
            )
            rows = cursor.fetchall()

            updated = 0
            for user_id, pin in rows:
                pin_str = str(pin).strip()
                if not pin_str:
                    continue

                pin_hash = bcrypt.hashpw(
                    pin_str.encode("utf-8"),
                    bcrypt.gensalt(),
                ).decode("utf-8")

                cursor.execute(
                    """
                    UPDATE users
                    SET pin_hash = %s,
                        failed_pin_attempts = 0,
                        locked_until = NULL
                    WHERE user_id = %s
                    """,
                    (pin_hash, int(user_id)),
                )
                updated += 1

        conn.commit()
        print(f"PIN hash migration complete: {updated} users updated")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
