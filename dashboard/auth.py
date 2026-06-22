"""
auth.py
-------
Autenticación de usuarios para IceStats.
Tabla `users` en PostgreSQL + bcrypt para hashing de contraseñas.
"""

import bcrypt
from sqlalchemy import text

ROLES = {
    "directivo":  "Directivo / Dueño de Franquicia",
    "entrenador": "Entrenador",
    "reclutador": "Reclutador",
}

_USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL       PRIMARY KEY,
    username      VARCHAR(50)  UNIQUE NOT NULL,
    name          VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL
                  CHECK (role IN ('directivo','entrenador','reclutador')),
    created_at    TIMESTAMP    DEFAULT NOW()
);
"""


def create_users_table(engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(_USERS_DDL))
        conn.commit()


def username_exists(engine, username: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM users WHERE username = :u"),
            {"u": username.strip().lower()},
        ).fetchone()
    return row is not None


def register_user(engine, username: str, name: str, password: str, role: str) -> tuple[bool, str]:
    """Crea un usuario. Retorna (True, '') o (False, mensaje_de_error)."""
    username = username.strip().lower()
    if len(username) < 3:
        return False, "El usuario debe tener al menos 3 caracteres."
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."
    if username_exists(engine, username):
        return False, "Ese nombre de usuario ya está en uso."
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO users (username, name, password_hash, role) "
                 "VALUES (:u, :n, :p, :r)"),
            {"u": username, "n": name.strip(), "p": hashed, "r": role},
        )
        conn.commit()
    return True, ""


def login_user(engine, username: str, password: str):
    """Verifica credenciales. Retorna dict {username, name, role} o None."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT name, password_hash, role FROM users WHERE username = :u"),
            {"u": username.strip().lower()},
        ).fetchone()
    if row is None:
        return None
    name, hashed, role = row
    if bcrypt.checkpw(password.encode(), hashed.encode()):
        return {"username": username.strip().lower(), "name": name, "role": role}
    return None
