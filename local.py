import asyncio
import functools
import logging
import shutil

from aiortc import RTCPeerConnection
from aiortc.contrib.media import MediaPlayer, MediaRecorder


def out(message, align):
    width, _ = shutil.get_terminal_size()
    width = max(15, width - 26)
    message = f"{{:.{align}{width}}}".format(message)
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

    @pc.on("track")
    async def _(track) -> None:
        print("Track added")

        @track.on("ended")
        async def on_ended():
            print("Track ended")

    return pc


async def server_loop(channel):
    print = print_server
    pc = connection(print_server)
    print("Waiting for offer")
    offer = await channel.recv()
    print("Offer received")
    await pc.setRemoteDescription(offer)
    print("Preparing video feed")
    player = MediaPlayer(
        "/dev/video0",
        format="v4l2",
        options={"framerate": "30", "video_size": "640x480"},
    )
    pc.addTrack(player.video)
    print("Video feed prepared")

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    answer = pc.localDescription
    print("Sending answer")
    await channel.send(answer)
    print("Answer sent")
    await asyncio.sleep(2)
    print("Server exit")
    await pc.close()
    player.video.stop()


async def client_loop(channel):
    print = print_client
    pc = connection(print_client)
    pc.addTransceiver("video", direction="recvonly")
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    @pc.on("track")
    async def _(track) -> None:
        print("Recording video!")
        recorder = MediaRecorder("./video.mp4")
        recorder.addTrack(track)
        await recorder.start()

        @track.on("ended")
        async def on_ended():
            print("Stop recording")
            await recorder.stop()

    offer = pc.localDescription
    print("Sending offer")
    await channel.send(offer)
    print("Offer sent")
    print("Waiting for answer")
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
    print_server("server")
    print_client("client")
    channel = create_channel()
    serv = asyncio.create_task(server_loop(channel))
    cl = asyncio.create_task(client_loop(channel))

    await asyncio.gather(serv, cl)


logging.basicConfig(level="WARNING", format="%(asctime)-15s: %(message)s")

if __name__ == "__main__":
    asyncio.run(main())
