# RTChat

A real-time multi-user chat application built with Python WebSockets and a modern browser UI.

## Features

- **Multi-user chat** — everyone in a room sees messages instantly
- **Chat rooms** — `#general`, `#random`, `#tech`, `#gaming`
- **Usernames** — pick a name when you join
- **Online presence** — see who's in the room
- **Typing indicators** — know when someone is typing
- **Message history** — last 100 messages per room are kept in memory
- **Auto-reconnect** — client reconnects automatically if the connection drops
- **Built-in web server** — no need to open `index.html` manually

## Prerequisites

- Python 3.10+
- `websockets` package

## Setup

```bash
pip install -r requirements.txt
```

## Run

Start the server:

```bash
python server.py
```

Open your browser to:

```
http://localhost:8000
```

Open multiple tabs or share the URL with others on your network to chat together.

## How it works

### Message protocol (JSON over WebSocket)

| Type | Direction | Description |
|------|-----------|-------------|
| `join` | Client → Server | Join with username and room |
| `chat` | Client → Server | Send a message |
| `typing` | Client → Server | Typing on/off |
| `switch_room` | Client → Server | Move to another room |
| `welcome` | Server → Client | Join confirmation + history |
| `chat` | Server → Client | Broadcast message |
| `system` | Server → Client | Join/leave notifications |
| `users` | Server → Client | Online user list |
| `typing` | Server → Client | Someone is typing |
| `room_changed` | Server → Client | Room switch confirmation |

### Architecture

```
Browser clients  ←→  WebSocket server (port 8000)
                          ├── Room: general
                          ├── Room: random
                          ├── Room: tech
                          └── Room: gaming
```

Each room maintains its own message history and user list. Messages are broadcast to all connected clients in the same room.

## Troubleshooting

- **Can't connect** — make sure `python server.py` is running
- **Port in use** — another process may be using port 8000; stop it or change the port in `server.py`
- **Messages not appearing** — confirm you joined with a username (the login screen must be completed)

## Notes

- Message history is stored in memory and resets when the server restarts
- No authentication — usernames are chosen freely
- Designed for local/LAN use; for production you'd want TLS, auth, and a persistent database