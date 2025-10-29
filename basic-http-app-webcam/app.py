import argparse
import asyncio
import logging

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRelay

PAGE = """\
<!DOCTYPE html>
<html>

<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>WebRTC webcam</title>
</head>

<body>
  <p><button id="start_stop" onclick="start_stop()">Start</button></p>
  <video id="video" autoplay="true" playsinline="true"></video>
  <script>
var pc = null;

async function start_stop() {
    const btnElem = document.getElementById('start_stop');
    if (btnElem.textContent === "Stop") {
        btnElem.textContent = "Start";
        pc.close()
        return
    }
    pc = new RTCPeerConnection({sdpSemantics: 'unified-plan'});
    pc.addEventListener('track', evt => {
        document.getElementById('video').srcObject = evt.streams[0]
    });
    pc.addTransceiver('video', { direction: 'recvonly' });

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    const response = await fetch('/offer', {
        body: JSON.stringify(offer),
        headers: {'Content-Type': 'application/json'},
        method: 'POST'
    });

    const answer = await response.json();
    await pc.setRemoteDescription(answer);
    btnElem.textContent = "Stop"
}
  </script>
</body>

</html>
"""

pcs = set()
relay = None
webcam = None


def create_track():
    global relay, webcam
    if relay is None:
        webcam = MediaPlayer(
            f"/dev/video{args.device}",
            format="v4l2",
            options={"framerate": "30", "video_size": "640x480"},
        )
        relay = MediaRelay()
    return relay.subscribe(webcam.video, False)


async def index(request: web.Request) -> web.Response:
    return web.Response(content_type="text/html", text=PAGE)


async def offer(request: web.Request) -> web.Response:
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)
    logging.info(f"New Connection! Active clients: {len(pcs)}")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange() -> None:
        logging.info(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)
        elif pc.connectionState == "closed":
            pcs.discard(pc)

    video = create_track()
    pc.addTrack(video)

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )


async def on_shutdown(app: web.Application) -> None:
    await asyncio.gather(*(pc.close() for pc in pcs))
    pcs.clear()
    if webcam is not None:
        webcam.video.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam demo")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument("--device", type=int, default=0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s %(levelname)-5s %(name)s: %(message)s",
    )

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_post("/offer", offer)
    web.run_app(app, host=args.host, port=args.port)
