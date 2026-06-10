import websockets
import asyncio
from websockets.asyncio.server import serve

async def sender_task(websocket):
    while True:
        reply = await asyncio.to_thread(input,"Enter the reply message:")
        await websocket.send(reply)
        print(f"sent a reply :{reply}")

async def receiver_task(websocket):
    while True:
        mmessage= await websocket.recv()
        print(f"received a message{mmessage}")

async def handler(websocket):
    #i can create task 
    send_task=asyncio.create_task(sender_task(websocket))
    recv_task=asyncio.create_task(receiver_task(websocket))
    
    #task mee we can add completion and pending 
    completed,pending=await asyncio.wait([recv_task,send_task],return_when = asyncio.FIRST_COMPLETED)

async def main():
    async with serve(handler,"",8000) as server:
        await server.serve_forever()
asyncio.run(main())