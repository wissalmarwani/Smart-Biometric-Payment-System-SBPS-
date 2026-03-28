import os
from dotenv import load_dotenv
from psycopg2.pool import SimpleConnectionPool

load_dotenv()


class DBConfigError(RuntimeError):
    """Raised when database configuration is missing or invalid."""


def create_connection_pool(min_conn=1, max_conn=20):
    """Create a PostgreSQL connection pool from environment variables."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise DBConfigError("DATABASE_URL is not set")

    try:
        return SimpleConnectionPool(min_conn, max_conn, database_url)
    except Exception as exc:
        raise DBConfigError(
            f"Failed to create PostgreSQL pool: {exc}"
        ) from exc
