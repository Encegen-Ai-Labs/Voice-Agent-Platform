from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.pipeline import VoicePipeline, AgentConfig

router = APIRouter(tags=["WebSocket"])

pipeline = VoicePipeline(AgentConfig())


@router.websocket("/ws/call")
async def websocket_call(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            audio_bytes = await websocket.receive_bytes()
            response_audio = await pipeline.process_audio(audio_bytes)
            await websocket.send_bytes(response_audio)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
