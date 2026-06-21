import asyncio
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

BASE_DIR = Path(__file__).parent
MAX_HISTORY = 100
ROOMS = ["general", "random", "tech", "gaming"]
TYPING_TIMEOUT = 3.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatServer:
    def __init__(self) -> None:
        self.clients: dict[object, dict] = {}
        self.rooms: dict[str, set[object]] = defaultdict(set)
        self.history: dict[str, list[dict]] = defaultdict(list)
        self.typing: dict[str, dict[str, asyncio.Task]] = defaultdict(dict)

    async def register(self, websocket, username: str, room: str) -> None:
        if room not in ROOMS:
            room = "general"

        self.clients[websocket] = {
            "id": str(uuid.uuid4()),
            "username": username,
            "room": room,
        }
        self.rooms[room].add(websocket)

        await self.send(websocket, {
            "type": "welcome",
            "username": username,
            "room": room,
            "rooms": ROOMS,
            "history": self.history[room][-MAX_HISTORY:],
            "users": self.room_users(room),
        })

        await self.broadcast(room, {
            "type": "system",
            "text": f"{username} joined the chat",
            "timestamp": now_iso(),
        }, exclude=websocket)

        await self.broadcast_users(room)

    async def unregister(self, websocket) -> None:
        client = self.clients.pop(websocket, None)
        if not client:
            return

        room = client["room"]
        username = client["username"]
        self.rooms[room].discard(websocket)
        self.clear_typing(room, username)

        await self.broadcast(room, {
            "type": "system",
            "text": f"{username} left the chat",
            "timestamp": now_iso(),
        })
        await self.broadcast_users(room)

    def room_users(self, room: str) -> list[str]:
        return sorted(
            self.clients[ws]["username"]
            for ws in self.rooms[room]
            if ws in self.clients
        )

    async def send(self, websocket, payload: dict) -> None:
        try:
            await websocket.send(json.dumps(payload))
        except ConnectionClosed:
            pass

    async def broadcast(self, room: str, payload: dict, exclude=None) -> None:
        message = json.dumps(payload)
        for ws in list(self.rooms[room]):
            if ws is exclude:
                continue
            try:
                await ws.send(message)
            except ConnectionClosed:
                await self.unregister(ws)

    async def broadcast_users(self, room: str) -> None:
        await self.broadcast(room, {
            "type": "users",
            "users": self.room_users(room),
        })

    def store_message(self, room: str, message: dict) -> None:
        self.history[room].append(message)
        if len(self.history[room]) > MAX_HISTORY:
            self.history[room] = self.history[room][-MAX_HISTORY:]

    async def handle_chat(self, websocket, text: str) -> None:
        client = self.clients.get(websocket)
        if not client or not text.strip():
            return

        message = {
            "type": "chat",
            "id": str(uuid.uuid4()),
            "username": client["username"],
            "text": text.strip(),
            "timestamp": now_iso(),
            "room": client["room"],
        }
        self.store_message(client["room"], message)
        self.clear_typing(client["room"], client["username"])
        await self.broadcast(client["room"], message)

    async def handle_typing(self, websocket, is_typing: bool) -> None:
        client = self.clients.get(websocket)
        if not client:
            return

        room = client["room"]
        username = client["username"]

        if is_typing:
            if username not in self.typing[room]:
                task = asyncio.create_task(self.typing_expired(room, username))
                self.typing[room][username] = task
            await self.broadcast(room, {
                "type": "typing",
                "username": username,
                "is_typing": True,
            }, exclude=websocket)
        else:
            self.clear_typing(room, username)
            await self.broadcast(room, {
                "type": "typing",
                "username": username,
                "is_typing": False,
            }, exclude=websocket)

    def clear_typing(self, room: str, username: str) -> None:
        task = self.typing[room].pop(username, None)
        if task and not task.done():
            task.cancel()

    async def typing_expired(self, room: str, username: str) -> None:
        await asyncio.sleep(TYPING_TIMEOUT)
        self.typing[room].pop(username, None)
        await self.broadcast(room, {
            "type": "typing",
            "username": username,
            "is_typing": False,
        })

    async def switch_room(self, websocket, new_room: str) -> None:
        client = self.clients.get(websocket)
        if not client or new_room not in ROOMS or new_room == client["room"]:
            return

        old_room = client["room"]
        username = client["username"]

        self.rooms[old_room].discard(websocket)
        self.clear_typing(old_room, username)
        client["room"] = new_room
        self.rooms[new_room].add(websocket)

        await self.broadcast(old_room, {
            "type": "system",
            "text": f"{username} left the chat",
            "timestamp": now_iso(),
        })
        await self.broadcast_users(old_room)

        await self.send(websocket, {
            "type": "room_changed",
            "room": new_room,
            "history": self.history[new_room][-MAX_HISTORY:],
            "users": self.room_users(new_room),
        })

        await self.broadcast(new_room, {
            "type": "system",
            "text": f"{username} joined the chat",
            "timestamp": now_iso(),
        })
        await self.broadcast_users(new_room)

    async def handle_message(self, websocket, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self.send(websocket, {
                "type": "error",
                "text": "Invalid message format",
            })
            return

        msg_type = data.get("type")

        if msg_type == "join":
            username = (data.get("username") or "").strip()[:24]
            room = data.get("room", "general")
            if not username:
                await self.send(websocket, {"type": "error", "text": "Username required"})
                return
            await self.register(websocket, username, room)
        elif msg_type == "chat":
            await self.handle_chat(websocket, data.get("text", ""))
        elif msg_type == "typing":
            await self.handle_typing(websocket, bool(data.get("is_typing")))
        elif msg_type == "switch_room":
            await self.switch_room(websocket, data.get("room", ""))
        else:
            await self.send(websocket, {"type": "error", "text": "Unknown message type"})


chat_server = ChatServer()


async def process_request(connection, request):
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None

    if request.path in ("/", "/index.html"):
        html_path = BASE_DIR / "index.html"
        if not html_path.exists():
            return connection.respond(404, "Not found\n")
        response = connection.respond(200, html_path.read_text(encoding="utf-8"))
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response
    return None


async def handler(websocket):
    try:
        async for message in websocket:
            if websocket not in chat_server.clients:
                data = json.loads(message)
                if data.get("type") != "join":
                    await chat_server.send(websocket, {
                        "type": "error",
                        "text": "Send a join message first",
                    })
                    continue
            await chat_server.handle_message(websocket, message)
    except ConnectionClosed:
        pass
    finally:
        await chat_server.unregister(websocket)


async def main():
    host = "localhost"
    port = 8000
    print(f"RTChat server running at http://{host}:{port}")
    print(f"Rooms: {', '.join(ROOMS)}")
    async with serve(
        handler,
        host,
        port,
        process_request=process_request,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())