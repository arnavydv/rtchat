import websockets
import asyncio
from websockets.asyncio.server import serve
#web socket - 2 function 
"""
handler - how the input/ouput handles 
main function - actually handles web socket new connection and requests made by 
client 
"""

async def handler(websocket):
    while True:
        message= await websocket.recv()
        print(f"received message:{message}")
async def main():
    async with serve(handler,"",8000) as server:
        await server.serve_forever()
asyncio.run(main())