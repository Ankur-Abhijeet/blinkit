"""
discovery.api.accounts — Account persistence for the storefront simulator.

Backs the signup / login / account screens with a small SQLite database:
  users            — username + salted password verifier (signin verification details)
  sessions         — opaque bearer tokens handed out by signup/login
  orders           — purchase history (one row per placed order)
  order_items      — line items belonging to an order
  location_history — every delivery location the account has used

Signup carries over whatever the guest session accumulated before the account
existed (location history + any orders placed in the session), so a brand-new
account starts out with the history that produced it.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _resolve_db_path() -> str:
    """Project root when it is writable, /tmp when it is not.

    Serverless hosts (Vercel, Lambda) mount the deployment read-only and give
    you only /tmp, so writing to the project directory raises "unable to open
    database file" on the first request. Set BLINKIT_DB_PATH to override.
    """
    override = os.environ.get("BLINKIT_DB_PATH")
    if override:
        return override

    project_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "blinkit_accounts.db"))
    if os.access(os.path.dirname(project_db), os.W_OK):
        return project_db

    return os.path.join(tempfile.gettempdir(), "blinkit_accounts.db")


DB_PATH = _resolve_db_path()

PBKDF2_ITERATIONS = 120_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    placed_at   TEXT NOT NULL,
    total_paise INTEGER NOT NULL,
    location    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sku_id      INTEGER NOT NULL,
    name        TEXT NOT NULL,
    pack        TEXT NOT NULL DEFAULT '',
    emoji       TEXT NOT NULL DEFAULT '',
    qty         INTEGER NOT NULL,
    price_paise INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS location_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    location    TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'session',
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_location_user ON location_history(user_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    """Salted PBKDF2-SHA256 verifier. The raw password is never stored."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return {"salt": salt, "hash": digest.hex()}


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    candidate = hash_password(password, salt)["hash"]
    return hmac.compare_digest(candidate, expected_hash)


# ---------------------------------------------------------------------------
# Payload models
# ---------------------------------------------------------------------------


class OrderItemPayload(BaseModel):
    sku_id: int
    name: str
    pack: str = ""
    emoji: str = ""
    qty: int = 1
    price_paise: int = 0


class OrderPayload(BaseModel):
    items: List[OrderItemPayload] = Field(default_factory=list)
    total_paise: int = 0
    location: str = ""
    placed_at: Optional[str] = None


class LocationEntryPayload(BaseModel):
    location: str
    source: str = "session"
    recorded_at: Optional[str] = None


class SignupPayload(BaseModel):
    username: str = Field(..., min_length=3, max_length=40)
    password: str = Field(..., min_length=4, max_length=128)
    # Guest-session history carried into the brand-new account record.
    location_history: List[LocationEntryPayload] = Field(default_factory=list)
    purchase_history: List[OrderPayload] = Field(default_factory=list)


class LoginPayload(BaseModel):
    username: str = Field(..., min_length=1, max_length=40)
    password: str = Field(..., min_length=1, max_length=128)


class LocationPayload(BaseModel):
    location: str
    source: str = "session"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _issue_token(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
        (token, user_id, _now()),
    )
    return token


def _record_location(conn: sqlite3.Connection, user_id: int, location: str, source: str, recorded_at: Optional[str] = None) -> None:
    location = (location or "").strip()
    if not location:
        return
    # Skip consecutive duplicates so the history reads as actual movement.
    last = conn.execute(
        "SELECT location FROM location_history WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if last and last["location"] == location:
        return
    conn.execute(
        "INSERT INTO location_history (user_id, location, source, recorded_at) VALUES (?, ?, ?, ?)",
        (user_id, location, source, recorded_at or _now()),
    )


def _insert_order(conn: sqlite3.Connection, user_id: int, order: OrderPayload) -> int:
    cur = conn.execute(
        "INSERT INTO orders (user_id, placed_at, total_paise, location) VALUES (?, ?, ?, ?)",
        (user_id, order.placed_at or _now(), order.total_paise, (order.location or "").strip()),
    )
    order_id = int(cur.lastrowid)
    conn.executemany(
        "INSERT INTO order_items (order_id, sku_id, name, pack, emoji, qty, price_paise) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(order_id, i.sku_id, i.name, i.pack, i.emoji, i.qty, i.price_paise) for i in order.items],
    )
    if order.location:
        _record_location(conn, user_id, order.location, "order", order.placed_at)
    return order_id


def _user_public(row: sqlite3.Row) -> Dict[str, Any]:
    return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}


def _resolve_token(authorization: Optional[str]) -> sqlite3.Row:
    """Maps a `Bearer <token>` header to its user row, or raises 401."""
    token = ""
    if authorization:
        parts = authorization.split(None, 1)
        token = parts[1].strip() if len(parts) == 2 and parts[0].lower() == "bearer" else authorization.strip()

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")

    conn = connect()
    try:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (token,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired, please sign in again")
    return row


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

router = APIRouter(tags=["accounts"])


@router.post("/v1/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupPayload):
    """Creates the account record: verification details + location & purchase history."""
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    conn = connect()
    try:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That username is already taken. Try logging in instead.")

        creds = hash_password(payload.password)
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?)",
            (username, creds["hash"], creds["salt"], _now()),
        )
        user_id = int(cur.lastrowid)

        for entry in payload.location_history:
            _record_location(conn, user_id, entry.location, entry.source, entry.recorded_at)

        for order in payload.purchase_history:
            _insert_order(conn, user_id, order)

        token = _issue_token(conn, user_id)
        conn.commit()

        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return {"token": token, "user": _user_public(row)}
    finally:
        conn.close()


@router.post("/v1/auth/login")
def login(payload: LoginPayload):
    """Validates username + password against the stored verifier."""
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (payload.username.strip(),)).fetchone()
        if not row or not verify_password(payload.password, row["password_salt"], row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

        token = _issue_token(conn, row["id"])
        conn.commit()
        return {"token": token, "user": _user_public(row)}
    finally:
        conn.close()


@router.post("/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(authorization: Optional[str] = Header(None)):
    token = ""
    if authorization:
        parts = authorization.split(None, 1)
        token = parts[1].strip() if len(parts) == 2 and parts[0].lower() == "bearer" else authorization.strip()

    if token:
        conn = connect()
        try:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()
    return None


@router.post("/v1/orders", status_code=status.HTTP_201_CREATED)
def place_order(payload: OrderPayload, authorization: Optional[str] = Header(None)):
    """Appends a placed order to the signed-in account's purchase history."""
    user = _resolve_token(authorization)
    conn = connect()
    try:
        order_id = _insert_order(conn, user["id"], payload)
        conn.commit()
        return {"order_id": order_id, "placed_at": payload.placed_at or _now(), "total_paise": payload.total_paise}
    finally:
        conn.close()


@router.post("/v1/account/location", status_code=status.HTTP_201_CREATED)
def add_location(payload: LocationPayload, authorization: Optional[str] = Header(None)):
    """Appends a delivery location to the signed-in account's location history."""
    user = _resolve_token(authorization)
    conn = connect()
    try:
        _record_location(conn, user["id"], payload.location, payload.source)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/v1/account")
def get_account(authorization: Optional[str] = Header(None)):
    """Account page payload: account name + order history (+ location history)."""
    user = _resolve_token(authorization)
    conn = connect()
    try:
        order_rows = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC",
            (user["id"],),
        ).fetchall()

        orders: List[Dict[str, Any]] = []
        for o in order_rows:
            item_rows = conn.execute(
                "SELECT sku_id, name, pack, emoji, qty, price_paise FROM order_items WHERE order_id = ? ORDER BY id",
                (o["id"],),
            ).fetchall()
            orders.append({
                "order_id": o["id"],
                "placed_at": o["placed_at"],
                "total_paise": o["total_paise"],
                "location": o["location"],
                "items": [dict(i) for i in item_rows],
            })

        loc_rows = conn.execute(
            "SELECT location, source, recorded_at FROM location_history WHERE user_id = ? ORDER BY id DESC",
            (user["id"],),
        ).fetchall()

        return {
            "user": _user_public(user),
            "order_count": len(orders),
            "orders": orders,
            "location_history": [dict(r) for r in loc_rows],
        }
    finally:
        conn.close()
