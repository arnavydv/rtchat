# rtchat

Real-time chat application using WebSockets (Python + browser UI).

## How it works

- The browser loads `index.html` and connects to the Python WebSocket server at:
  - `ws://localhost:8000`
- When you send a message from the browser UI, it is delivered to the server and printed in the server terminal.
- The server terminal can send “reply” messages back to the connected browser client by typing into the server prompt.

## Prerequisites

- Python 3.x
- `websockets` package

## Setup

Install dependencies:

```bash
pip install websockets
```

## Run

1. Start the server:

```bash
python server.py
```

2. Open the client in your browser:

- Open `index.html` (so it can connect to `ws://localhost:8000`)

## Usage

- In the browser:
  - Type a message in the input box and press **Send** (or press **Enter**).
  - You will see your sent message and any received messages as chat bubbles.
- In the terminal where `server.py` is running:
  - When prompted with `Enter the reply message:`, type a reply and press Enter.
  - That reply is sent back to the connected browser.

## WebSocket message flow

- Browser → Server: `ws.send(text)`
- Server → Browser: `websocket.send(reply)` (triggered from the server terminal input)

## Troubleshooting

- **Client shows “Connecting…” but never connects**
  - Make sure `server.py` is running.
  - Ensure the port `8000` is reachable on your machine.
- **WebSocket connection failure**
  - Confirm the URL is correct (`ws://localhost:8000`).
  - Check that another process is not already using port `8000`.
- **No replies arrive**
  - Remember: replies are typed manually in the server terminal (the server doesn’t auto-respond).

## Notes / current limitations

- This is a single-server, single-connection chat flow (not a multi-room chat system).
- The server’s “reply” side is driven by interactive terminal input (`input()`), so it acts more like a demo than a fully automated chat bot.
