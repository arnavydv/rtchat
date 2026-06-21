import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "rtchat.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS room_messages (
                id TEXT PRIMARY KEY,
                room TEXT NOT NULL,
                username TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                edited INTEGER DEFAULT 0,
                deleted INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_room_messages_room
                ON room_messages(room, timestamp);

            CREATE TABLE IF NOT EXISTS room_reactions (
                message_id TEXT NOT NULL,
                username TEXT NOT NULL,
                emoji TEXT NOT NULL,
                PRIMARY KEY (message_id, username, emoji),
                FOREIGN KEY (message_id) REFERENCES room_messages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS dm_messages (
                id TEXT PRIMARY KEY,
                dm_key TEXT NOT NULL,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                edited INTEGER DEFAULT 0,
                deleted INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_dm_messages_key
                ON dm_messages(dm_key, timestamp);

            CREATE TABLE IF NOT EXISTS dm_reactions (
                message_id TEXT NOT NULL,
                username TEXT NOT NULL,
                emoji TEXT NOT NULL,
                PRIMARY KEY (message_id, username, emoji),
                FOREIGN KEY (message_id) REFERENCES dm_messages(id) ON DELETE CASCADE
            );
        """)


def dm_key(user1: str, user2: str) -> str:
    return ":".join(sorted([user1, user2]))


def _reactions_for_messages(conn: sqlite3.Connection, table: str, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT message_id, username, emoji FROM {table} WHERE message_id IN ({placeholders})",
        ids,
    ).fetchall()
    result: dict[str, dict] = {}
    for row in rows:
        msg_id = row["message_id"]
        result.setdefault(msg_id, {}).setdefault(row["emoji"], []).append(row["username"])
    for msg_id in result:
        for emoji in result[msg_id]:
            result[msg_id][emoji].sort()
    return result


def _row_to_message(row: sqlite3.Row, reactions: dict, *, is_dm: bool = False) -> dict:
    msg = {
        "type": "dm" if is_dm else "chat",
        "id": row["id"],
        "username": row["sender"] if is_dm else row["username"],
        "text": row["text"],
        "timestamp": row["timestamp"],
        "edited": bool(row["edited"]),
        "deleted": bool(row["deleted"]),
        "reactions": reactions.get(row["id"], {}),
    }
    if is_dm:
        msg["sender"] = row["sender"]
        msg["recipient"] = row["recipient"]
        msg["dm_key"] = row["dm_key"]
    else:
        msg["room"] = row["room"]
    return msg


def save_room_message(message: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO room_messages (id, room, username, text, timestamp) VALUES (?, ?, ?, ?, ?)",
            (message["id"], message["room"], message["username"], message["text"], message["timestamp"]),
        )


def save_dm_message(message: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO dm_messages
               (id, dm_key, sender, recipient, text, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                message["id"],
                message["dm_key"],
                message["sender"],
                message["recipient"],
                message["text"],
                message["timestamp"],
            ),
        )


def get_room_history(room: str, limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM room_messages
               WHERE room = ? ORDER BY timestamp DESC LIMIT ?""",
            (room, limit),
        ).fetchall()
        rows = list(reversed(rows))
        ids = [r["id"] for r in rows]
        reactions = _reactions_for_messages(conn, "room_reactions", ids)
        return [_row_to_message(r, reactions) for r in rows]


def get_dm_history(user1: str, user2: str, limit: int = 100) -> list[dict]:
    key = dm_key(user1, user2)
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM dm_messages
               WHERE dm_key = ? ORDER BY timestamp DESC LIMIT ?""",
            (key, limit),
        ).fetchall()
        rows = list(reversed(rows))
        ids = [r["id"] for r in rows]
        reactions = _reactions_for_messages(conn, "dm_reactions", ids)
        return [_row_to_message(r, reactions, is_dm=True) for r in rows]


def get_room_message(message_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM room_messages WHERE id = ?", (message_id,)).fetchone()
        if not row:
            return None
        reactions = _reactions_for_messages(conn, "room_reactions", [message_id])
        return _row_to_message(row, reactions)


def get_dm_message(message_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM dm_messages WHERE id = ?", (message_id,)).fetchone()
        if not row:
            return None
        reactions = _reactions_for_messages(conn, "dm_reactions", [message_id])
        return _row_to_message(row, reactions, is_dm=True)


def toggle_room_reaction(message_id: str, username: str, emoji: str) -> dict | None:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM room_reactions WHERE message_id = ? AND username = ? AND emoji = ?",
            (message_id, username, emoji),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM room_reactions WHERE message_id = ? AND username = ? AND emoji = ?",
                (message_id, username, emoji),
            )
        else:
            conn.execute(
                "INSERT INTO room_reactions (message_id, username, emoji) VALUES (?, ?, ?)",
                (message_id, username, emoji),
            )
        reactions = _reactions_for_messages(conn, "room_reactions", [message_id])
        return reactions.get(message_id, {})


def toggle_dm_reaction(message_id: str, username: str, emoji: str) -> dict | None:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM dm_reactions WHERE message_id = ? AND username = ? AND emoji = ?",
            (message_id, username, emoji),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM dm_reactions WHERE message_id = ? AND username = ? AND emoji = ?",
                (message_id, username, emoji),
            )
        else:
            conn.execute(
                "INSERT INTO dm_reactions (message_id, username, emoji) VALUES (?, ?, ?)",
                (message_id, username, emoji),
            )
        reactions = _reactions_for_messages(conn, "dm_reactions", [message_id])
        return reactions.get(message_id, {})


def edit_room_message(message_id: str, text: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE room_messages SET text = ?, edited = 1 WHERE id = ? AND deleted = 0",
            (text, message_id),
        )
        return cur.rowcount > 0


def edit_dm_message(message_id: str, text: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE dm_messages SET text = ?, edited = 1 WHERE id = ? AND deleted = 0",
            (text, message_id),
        )
        return cur.rowcount > 0


def delete_room_message(message_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE room_messages SET deleted = 1, text = '' WHERE id = ?",
            (message_id,),
        )
        conn.execute("DELETE FROM room_reactions WHERE message_id = ?", (message_id,))
        return cur.rowcount > 0


def delete_dm_message(message_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE dm_messages SET deleted = 1, text = '' WHERE id = ?",
            (message_id,),
        )
        conn.execute("DELETE FROM dm_reactions WHERE message_id = ?", (message_id,))
        return cur.rowcount > 0