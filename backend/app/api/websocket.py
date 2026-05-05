import json
import base64
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.pipeline import VoicePipeline, AgentConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

pipeline = VoicePipeline(AgentConfig())


@router.websocket("/ws/call")
async def websocket_call(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")

            if event == "media":
                audio_bytes = base64.b64decode(data["media"]["payload"])
                response_audio = await pipeline.process_audio(audio_bytes)
                await websocket.send_text(json.dumps({
                    "event": "media",
                    "media": {"payload": base64.b64encode(response_audio).decode("utf-8")},
                }))
            elif event in ("connected", "start", "stop"):
                logger.info("Twilio event: %s", event)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
