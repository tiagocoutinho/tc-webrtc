import asyncio
import functools
import logging
import shutil

from aiortc import RTCPeerConnection


def out(message, align, ch=" "):
    width, _ = shutil.get_terminal_size()
    width = max(15, width - 26)
    message = f"{{:{ch}{align}{width}}}".format(message)
    logging.warning(message)


print_server = functools.partial(out, align="<")
print_client = functools.partial(out, align=">")


def connection(print):
    pc = RTCPeerConnection()

    @pc.on("connectionstatechange")
    async def _() -> None:
        print(f"Connection state changed to: {pc.connectionState}")

    @pc.on("iceconnectionstatechange")
    async def _() -> None:
        print(f"ICE Connection state changed to: {pc.iceConnectionState}")

    @pc.on("icegatheringstatechange")
    async def _() -> None:
        print(f"ICE gathering state changed to: {pc.iceGatheringState}")

    @pc.on("signalingstatechange")
    async def _() -> None:
        print(f"Signaling state changed to: {pc.signalingState}")

    return pc


async def server_loop(channel):
    print = print_server
    pc = connection(print_server)

    @pc.on("datachannel")
    def on_datachannel(channel):
        print(f"Data channel '{channel.label}' opened.")

        @channel.on("message")
        def on_message(message):
            print(f"Received message on '{channel.label}': {message}")
            channel.send("Hello from answerer!!!")

    print("Waiting for offer...")
    offer = await channel.recv()
    print("Offer received")
    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    answer = pc.localDescription
    print("Sending answer...")
    await channel.send(answer)
    print("Answer sent")
    await asyncio.sleep(2)
    print("Server exit")
    await pc.close()



async def client_loop(channel):
    print = print_client
    pc = connection(print_client)
    
    dc = pc.createDataChannel("chat")

    @dc.on("open")
    def on_open():
        print("Data channel open. Sending message...")
        dc.send("Hello from offerer!")

    @dc.on("message")
    def on_message(message):
        print(f"Received message on '{dc.label}': {message}")

    print("Creating offer...")
    offer = await pc.createOffer()
    print("Offer created")

    print("Setting local offer...")
    await pc.setLocalDescription(offer)
    print("Local offer set")
    print("Sending offer...")
    await channel.send(offer)
    print("Offer sent")
    print("Waiting for answer...")
    answer = await channel.recv()
    print("Answer received")
    await pc.setRemoteDescription(answer)
    await asyncio.sleep(2)
    print("Client exit")
    await pc.close()


def create_channel():
    channel = asyncio.Queue()

    async def send(message):
        await channel.put(message)
        await channel.join()

    async def recv():
        message = await channel.get()
        channel.task_done()
        return message

    channel.send = send
    channel.recv = recv
    return channel


async def main():
    print_server("=== SERVER ===", ch=" ")
    print_client("=== CLIENT ===", ch=" ")
    channel = create_channel()
    serv = asyncio.create_task(server_loop(channel))
    cl = asyncio.create_task(client_loop(channel))

    await asyncio.gather(serv, cl)


logging.basicConfig(level="WARNING", format="%(asctime)-15s: %(message)s")

if __name__ == "__main__":
    asyncio.run(main())
