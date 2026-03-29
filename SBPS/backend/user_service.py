from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import bcrypt

from db import create_connection_pool


class UserServiceError(RuntimeError):
    """Base service error."""


class UserNotFoundError(UserServiceError):
    """Raised when a user does not exist."""


class InsufficientBalanceError(UserServiceError):
    """Raised when user balance is lower than the requested amount."""

    def __init__(self, current_balance):
        self.current_balance = float(current_balance)
        super().__init__("Insufficient balance")


class InvalidPinError(UserServiceError):
    """Raised when PIN verification fails."""

    def __init__(self, remaining_attempts=None):
        self.remaining_attempts = remaining_attempts
        super().__init__("Invalid PIN")


class PinLockedError(UserServiceError):
    """Raised when user PIN entry is temporarily locked."""

    def __init__(self, locked_until, retry_after_seconds):
        self.locked_until = locked_until
        self.retry_after_seconds = retry_after_seconds
        super().__init__("PIN entry is temporarily locked")


class UserService:
    def __init__(self, min_conn=1, max_conn=20):
        self.pool = create_connection_pool(
            min_conn=min_conn,
            max_conn=max_conn,
        )

    @contextmanager
    def _cursor(self):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                yield conn, cursor
        finally:
            self.pool.putconn(conn)

    def count_users(self):
        with self._cursor() as (_, cursor):
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def list_users(self):
        with self._cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT user_id, name, face_path, balance
                FROM users
                WHERE is_active = TRUE
                ORDER BY user_id
                """
            )
            rows = cursor.fetchall()

        return [
            {
                "user_id": str(row[0]),
                "name": row[1],
                "face_path": row[2],
                "balance": float(row[3]),
            }
            for row in rows
        ]

    def get_user(self, user_id):
        with self._cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT user_id, name, face_path, balance, pin
                FROM users
                WHERE user_id = %s AND is_active = TRUE
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return {
            "user_id": str(row[0]),
            "name": row[1],
            "face_path": row[2],
            "balance": float(row[3]),
            "pin": str(row[4]) if row[4] is not None else "",
        }

    def verify_pin_secure(
        self,
        user_id,
        provided_pin,
        max_attempts=5,
        lock_seconds=300,
    ):
        pin = str(provided_pin or "").strip()
        if not pin:
            raise InvalidPinError(remaining_attempts=max_attempts)

        with self._cursor() as (conn, cursor):
            cursor.execute(
                """
                SELECT
                    user_id,
                    name,
                    face_path,
                    balance,
                    pin,
                    pin_hash,
                    COALESCE(failed_pin_attempts, 0),
                    locked_until
                FROM users
                WHERE user_id = %s AND is_active = TRUE
                FOR UPDATE
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                raise UserNotFoundError("User not found")

            now = datetime.now(timezone.utc)
            locked_until = self._normalize_datetime(row[7])
            if locked_until and locked_until > now:
                retry_after = int((locked_until - now).total_seconds())
                conn.rollback()
                raise PinLockedError(
                    locked_until=locked_until,
                    retry_after_seconds=max(retry_after, 1),
                )

            stored_pin = str(row[4] or "").strip()
            stored_pin_hash = str(row[5] or "").strip()
            failed_attempts = int(row[6] or 0)

            if not stored_pin and not stored_pin_hash:
                conn.rollback()
                raise UserServiceError("PIN not configured for user")

            is_valid = False
            if stored_pin_hash:
                try:
                    is_valid = bcrypt.checkpw(
                        pin.encode("utf-8"),
                        stored_pin_hash.encode("utf-8"),
                    )
                except ValueError as exc:
                    conn.rollback()
                    raise UserServiceError(
                        "Stored PIN hash is invalid"
                    ) from exc
            else:
                is_valid = pin == stored_pin

            if is_valid:
                pin_hash = stored_pin_hash
                if not pin_hash:
                    pin_hash = bcrypt.hashpw(
                        pin.encode("utf-8"),
                        bcrypt.gensalt(),
                    ).decode("utf-8")

                cursor.execute(
                    """
                    UPDATE users
                    SET
                        pin_hash = %s,
                        failed_pin_attempts = 0,
                        locked_until = NULL
                    WHERE user_id = %s
                    """,
                    (pin_hash, int(user_id)),
                )
                conn.commit()

                return {
                    "user_id": str(row[0]),
                    "name": row[1],
                    "face_path": row[2],
                    "balance": float(row[3]),
                }

            failed_attempts += 1
            remaining_attempts = max(int(max_attempts) - failed_attempts, 0)
            if failed_attempts >= int(max_attempts):
                lock_until = now + timedelta(seconds=int(lock_seconds))
                lock_until_naive = lock_until.replace(tzinfo=None)
                cursor.execute(
                    """
                    UPDATE users
                    SET
                        failed_pin_attempts = %s,
                        locked_until = %s
                    WHERE user_id = %s
                    """,
                    (failed_attempts, lock_until_naive, int(user_id)),
                )
                conn.commit()
                raise PinLockedError(
                    locked_until=lock_until,
                    retry_after_seconds=max(int(lock_seconds), 1),
                )

            cursor.execute(
                """
                UPDATE users
                SET failed_pin_attempts = %s
                WHERE user_id = %s
                """,
                (failed_attempts, int(user_id)),
            )
            conn.commit()
            raise InvalidPinError(remaining_attempts=remaining_attempts)

    @staticmethod
    def _normalize_datetime(value):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_payment_atomic(self, user_id, amount):
        try:
            amount_decimal = Decimal(str(amount)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise UserServiceError("Amount must be a valid number") from exc

        if amount_decimal <= 0:
            raise UserServiceError("Amount must be greater than 0")

        with self._cursor() as (conn, cursor):
            try:
                cursor.execute(
                    """
                    SELECT name, balance
                    FROM users
                    WHERE user_id = %s AND is_active = TRUE
                    FOR UPDATE
                    """,
                    (int(user_id),),
                )
                row = cursor.fetchone()
                if not row:
                    raise UserNotFoundError("User not found")

                name, current_balance = row[0], Decimal(str(row[1]))
                if current_balance < amount_decimal:
                    raise InsufficientBalanceError(current_balance)

                new_balance = (
                    current_balance - amount_decimal
                ).quantize(Decimal("0.01"))

                cursor.execute(
                    "UPDATE users SET balance = %s WHERE user_id = %s",
                    (new_balance, int(user_id)),
                )

                cursor.execute(
                    """
                    INSERT INTO transactions (
                        user_id,
                        amount,
                        balance_before,
                        balance_after,
                        status
                    )
                    VALUES (%s, %s, %s, %s, 'completed')
                    """,
                    (
                        int(user_id),
                        amount_decimal,
                        current_balance,
                        new_balance,
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return {
            "user_id": str(user_id),
            "name": name,
            "amount": float(amount_decimal),
            "new_balance": float(new_balance),
            "current_balance": float(current_balance),
        }

    def list_transactions(self, limit=20):
        safe_limit = max(1, min(int(limit), 100))
        with self._cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT
                    transaction_id,
                    user_id,
                    amount,
                    balance_before,
                    balance_after,
                    status,
                    created_at
                FROM transactions
                ORDER BY transaction_id DESC
                LIMIT %s
                """,
                (safe_limit,),
            )
            rows = cursor.fetchall()

        return [
            {
                "transaction_id": int(row[0]),
                "user_id": str(row[1]),
                "amount": float(row[2]),
                "balance_before": float(row[3]),
                "balance_after": float(row[4]),
                "status": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
            }
            for row in rows
        ]
