import asyncio

from aiortc import RTCPeerConnection
from aiortc.contrib.media import MediaPlayer


async def main():
    pc1 = RTCPeerConnection()
    pc2 = RTCPeerConnection()

    @pc1.on("track")
    async def on_track1(track) -> None:
        print(f"PC1: track added: {track}")

    @pc1.on("connectionstatechange")
    async def on_connectionstatechange1() -> None:
        print(f"PC1: Conn state changed to: {pc1.connectionState}")

    @pc2.on("connectionstatechange")
    async def on_connectionstatechange2() -> None:
        print(f"PC2: Conn state changed to: {pc2.connectionState}")

    pc1.addTransceiver("video", direction="recvonly")
    mp = MediaPlayer("/dev/video10", format="v4l2")
    pc2.addTrack(mp.video)

    offer = await pc1.createOffer()
    await pc1.setLocalDescription(offer)
    await pc2.setRemoteDescription(offer)
    answer = await pc2.createAnswer()
    await pc2.setLocalDescription(answer)
    await pc1.setRemoteDescription(answer)

    await asyncio.sleep(10)


asyncio.run(main())