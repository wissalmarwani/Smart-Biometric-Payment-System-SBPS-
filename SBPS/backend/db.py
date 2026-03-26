# Gère la base de données avec sqlite3.
# PRAGMA key ne fonctionne que si SQLite est compilé avec SQLCipher.
import sqlite3
import bcrypt

DB_PATH = "sbps.db"


def get_connection():
    """Connecte à la base et tente PRAGMA key si SQLCipher est dispo."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "PRAGMA key = 'ton_mot_de_passe_AES256';"
    )  # clé de chiffrement
    return conn


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        pin_hash TEXT NOT NULL,
        face_encoding TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()


def add_user(name, phone, pin, face_encoding):
    conn = get_connection()
    cursor = conn.cursor()

    # Hash du PIN avec bcrypt
    pin_hash = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt())

    cursor.execute("""
    INSERT INTO users (name, phone, pin_hash, face_encoding)
    VALUES (?, ?, ?, ?)
    """, (name, phone, pin_hash, face_encoding))

    conn.commit()
    conn.close()


def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, phone, pin_hash, face_encoding FROM users"
    )
    users = cursor.fetchall()
    conn.close()
    return users


def find_user_by_phone(phone):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, phone, pin_hash, face_encoding "
        "FROM users WHERE phone = ?",
        (phone,),
    )
    user = cursor.fetchone()
    conn.close()
    return user
