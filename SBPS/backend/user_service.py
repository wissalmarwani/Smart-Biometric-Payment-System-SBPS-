from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

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

    def verify_pin_plaintext(self, user_id, provided_pin):
        user = self.get_user(user_id)
        if not user:
            raise UserNotFoundError("User not found")

        stored_pin = str(user.get("pin", "")).strip()
        if not stored_pin:
            return False, user

        return str(provided_pin).strip() == stored_pin, user

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
