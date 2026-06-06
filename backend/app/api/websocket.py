import asyncio
import audioop
import base64
import json
import logging
import os
import time
import traceback
import wave
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.pipeline import AgentConfig, VoicePipeline
from app.core.realtime_stt import RealtimeSTTClient
from app.database import SessionLocal
from app.models.agent import Agent
from app.models.call import Call
from app.models.knowledge_base import KnowledgeBase
from app.schemas.call import CallUpdate
from app.services.call_service import update_call

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter(tags=["WebSocket"])


_CHUNK_SIZE = 160


@router.websocket("/ws/call")
async def websocket_call(websocket: WebSocket):
    await websocket.accept()

    call_id: str | None = websocket.query_params.get("call_id")
    logger.info("[WS] Accepted call_id=%s", call_id)


    pipeline = VoicePipeline(AgentConfig())
    realtime_stt: RealtimeSTTClient | None = None

    stream_sid: str | None = None
    twilio_call_sid: str | None = None
    full_recording: bytearray = bytearray()       
    outbound_recording: bytearray = bytearray()   
    conversation_history: list[dict] = []

    ai_speaking: bool = False
    interrupt_event: asyncio.Event = asyncio.Event()
    response_task: asyncio.Task | None = None
    last_processed_transcript: str = ""
    pending_transcript: str | None = None  

    _DISCONNECTED = object()  


    async def _cancel_response_task() -> None:
        """Cancel and await the current response task if any."""
        nonlocal response_task, ai_speaking
        task = response_task
        if task is None or task.done():
            return
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=1.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        response_task = None
        ai_speaking = False

  
    async def on_realtime_transcript(transcript: str, event_type: str) -> None:
        nonlocal ai_speaking, interrupt_event, response_task
        nonlocal conversation_history, last_processed_transcript, stream_sid
        nonlocal pending_transcript

        transcript = transcript.strip()
        if not transcript:
            return

        print(f"[STT CALLBACK] [{event_type}] {transcript!r} | ai_speaking={ai_speaking} | stream_sid={stream_sid}")
        logger.info("[STT] [%s] %r", event_type, transcript)

        # ---- Interruption: user spoke while AI is talking ----
        if ai_speaking and event_type not in ("EndOfTurn", "EagerEndOfTurn"):
            print("[WS] Barge-in detected — cancelling response task")
            logger.info("[WS] Barge-in detected — cancelling response task")
            await _cancel_response_task()
            interrupt_event.set()
            if stream_sid:
                try:
                    await websocket.send_json({
                        "event": "clear",
                        "streamSid": stream_sid,
                    })
                except Exception as exc:
                    logger.warning("[WS] Twilio clear failed: %s", exc)

        if event_type not in ("EndOfTurn", "EagerEndOfTurn"):
            return

        if transcript == last_processed_transcript:
            print(f"[STT CALLBACK] Duplicate transcript, skipping: {transcript!r}")
            return

        if response_task and not response_task.done():
            print(f"[WS] Response running — queuing turn: {transcript!r}")
            logger.info("[WS] Response running — queuing turn: %r", transcript)
            pending_transcript = transcript
            return

        last_processed_transcript = transcript
        interrupt_event.clear()
        history_snapshot = list(conversation_history)

        print(f"[WS] Launching response task for: {transcript!r}")

        async def run_response(turn_transcript: str, turn_history: list) -> None:
            nonlocal ai_speaking, conversation_history, response_task
            nonlocal pending_transcript, last_processed_transcript

            ai_speaking = True
            assistant_parts: list[str] = []
            was_interrupted = False

            try:
                print(f"[WS] run_response START: {turn_transcript!r} | stream_sid={stream_sid}")
                logger.info("[WS] run_response START: %r", turn_transcript)
                t0 = time.time()

                async for sentence, audio in pipeline.stream_audio_sentences(
                    turn_transcript, turn_history
                ):
                    if interrupt_event.is_set():
                        logger.info("[WS] Interrupt flag set — stopping audio")
                        was_interrupted = True
                        break

                    assistant_parts.append(sentence)

                    for i in range(0, len(audio), _CHUNK_SIZE):
                        if interrupt_event.is_set():
                            was_interrupted = True
                            break

                        chunk = audio[i : i + _CHUNK_SIZE]
                        # Record AI audio for the combined recording
                        outbound_recording.extend(chunk)
                        try:
                            await websocket.send_json({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": base64.b64encode(chunk).decode()
                                },
                            })
                        except Exception as exc:
                            logger.error("[WS] Twilio send failed: %s", exc)
                            return

                        await asyncio.sleep(0)

                    if was_interrupted:
                        break

                if not was_interrupted and assistant_parts:
                    full_response = " ".join(assistant_parts)
                    pipeline.last_transcript = turn_transcript
                    pipeline.last_response = full_response

                    conversation_history.append({"role": "user", "content": turn_transcript})
                    conversation_history.append({"role": "assistant", "content": full_response})
                    conversation_history = conversation_history[-6:]
                    logger.info(
                        "[WS] History updated (%d msgs). Last response: %r",
                        len(conversation_history),
                        full_response,
                    )

                logger.info("[WS] run_response END (%.2fs)", time.time() - t0)

            except asyncio.CancelledError:
                logger.info("[WS] run_response CANCELLED")
                raise

            except Exception as exc:
                logger.error("[WS] run_response error: %s\n%s", exc, traceback.format_exc())

            finally:
                ai_speaking = False
                # Process any queued turn immediately after this one finishes
                queued = pending_transcript
                if queued and queued != last_processed_transcript:
                    pending_transcript = None
                    last_processed_transcript = queued
                    interrupt_event.clear()
                    queued_history = list(conversation_history)
                    logger.info("[WS] Processing queued turn: %r", queued)
                    response_task = asyncio.create_task(
                        run_response(queued, queued_history),
                        name="response-queued",
                    )
                else:
                    pending_transcript = None

        logger.info("[WS] Launching response task for: %r", transcript)
        response_task = asyncio.create_task(
            run_response(transcript, history_snapshot),
            name="response",
        )

    try:
        realtime_stt = RealtimeSTTClient(on_transcript=on_realtime_transcript)
        await realtime_stt.connect()
        logger.info("[WS] Realtime STT connected")
    except Exception as exc:
        logger.error("[WS] Realtime STT init failed: %s", exc)

    
    async def next_media_chunk() -> bytes | object:
       
        nonlocal stream_sid, twilio_call_sid

        while True:
            try:
                raw = await websocket.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                logger.info("[WS] WebSocket disconnected")
                return _DISCONNECTED

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("[WS] Non-JSON message received")
                continue

            event = data.get("event")

            if event == "media":
                audio_chunk = base64.b64decode(data["media"]["payload"])
                full_recording.extend(audio_chunk)

                if realtime_stt:
                    try:
                        await realtime_stt.send_audio(audio_chunk)
                    except Exception as exc:
                        logger.error("[WS] STT send error: %s", exc)

                return audio_chunk

            elif event == "start":
                start_data = data.get("start", {})
                stream_sid = data.get("streamSid") or start_data.get("streamSid")
                twilio_call_sid = (
                    data.get("callSid")
                    or start_data.get("callSid")
                )
                logger.info(
                    "[WS] Stream started sid=%s call_sid=%s",
                    stream_sid,
                    twilio_call_sid,
                )
                _load_agent_config(twilio_call_sid, pipeline)

            elif event == "stop":
                logger.info("[WS] Twilio stop event")
                return _DISCONNECTED

            return None  

  
    try:
        while True:
            chunk = await next_media_chunk()
            if chunk is _DISCONNECTED:
                break

    except Exception as exc:
        logger.error("[WS] Fatal error: %s\n%s", exc, traceback.format_exc())

    finally:
        await _cancel_response_task()

        if realtime_stt:
            await realtime_stt.close()

        _save_recording(full_recording, outbound_recording, twilio_call_sid)


def _load_agent_config(twilio_call_sid: str | None, pipeline: VoicePipeline) -> None:
    
    if not twilio_call_sid:
        return

    db = SessionLocal()
    try:
        call = db.query(Call).filter(
            Call.twilio_call_sid == twilio_call_sid
        ).first()

        if not call:
            logger.warning("[WS] No call found for sid=%s", twilio_call_sid)
            return

        agent = db.query(Agent).filter(
            Agent.id == call.agent_id,
            Agent.workspace_id == call.workspace_id,
        ).first()

        if not agent:
            logger.warning("[WS] No agent found for call %s", call.id)
            return

        pipeline.config.system_prompt = (
            agent.system_prompt or AgentConfig.system_prompt
        )
        pipeline.config.llm_model = agent.llm_model or AgentConfig.llm_model
        pipeline.config.language = agent.language or AgentConfig.language
        pipeline.config.agent_id = agent.id

        entries = (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.agent_id == agent.id)
            .order_by(KnowledgeBase.created_at.desc())
            .limit(3)
            .all()
        )
        pipeline.config.knowledge_context = "\n".join(
            e.content for e in entries if e.content
        )

        logger.info(
            "[WS] Agent config loaded: agent_id=%s model=%s lang=%s kb_entries=%d",
            agent.id,
            pipeline.config.llm_model,
            pipeline.config.language,
            len(entries),
        )

    except Exception as exc:
        logger.error("[WS] Agent config load failed: %s", exc)
    finally:
        db.close()


def _save_recording(
    inbound: bytearray,
    outbound: bytearray,
    twilio_call_sid: str | None,
) -> None:
 
    if not inbound and not outbound:
        logger.warning("[RECORDING] No audio captured — skipping save")
        return

    filename: str = (
        f"{twilio_call_sid}.wav"
        if twilio_call_sid
        else f"unknown_{int(time.time())}.wav"
    )

    try:
        recordings_dir = os.path.abspath("recordings")
        os.makedirs(recordings_dir, exist_ok=True)
        recording_path = os.path.join(recordings_dir, filename)

        
        inbound_pcm = audioop.ulaw2lin(bytes(inbound), 2) if inbound else b""
        outbound_pcm = audioop.ulaw2lin(bytes(outbound), 2) if outbound else b""

        inbound_samples = len(inbound_pcm) // 2
        outbound_samples = len(outbound_pcm) // 2
        max_samples = max(inbound_samples, outbound_samples)

        if inbound_samples < max_samples:
            inbound_pcm += b"\x00\x00" * (max_samples - inbound_samples)
        if outbound_samples < max_samples:
            outbound_pcm += b"\x00\x00" * (max_samples - outbound_samples)

        import struct
        stereo_frames = bytearray()
        for i in range(0, max_samples * 2, 2):
            stereo_frames += inbound_pcm[i:i+2]   # left (user)
            stereo_frames += outbound_pcm[i:i+2]  # right (AI)

        with wave.open(recording_path, "wb") as wav_file:
            wav_file.setnchannels(2)       # stereo
            wav_file.setsampwidth(2)       # 16-bit
            wav_file.setframerate(8000)    # 8kHz
            wav_file.writeframes(bytes(stereo_frames))

        duration_s = max_samples / 8000
        logger.info("=" * 60)
        logger.info("[RECORDING] Stereo WAV saved (L=user, R=AI)")
        logger.info("[RECORDING] Filename : %s", filename)
        logger.info("[RECORDING] Path     : %s", recording_path)
        logger.info("[RECORDING] Duration : %.1fs", duration_s)
        logger.info("[RECORDING] Inbound  : %d bytes", len(inbound))
        logger.info("[RECORDING] Outbound : %d bytes", len(outbound))
        logger.info("=" * 60)
        print(f"\n{'='*60}")
        print(f"[RECORDING] File: {recording_path}")
        print(f"[RECORDING] Duration: {duration_s:.1f}s  |  inbound={len(inbound)}B  outbound={len(outbound)}B")
        print(f"{'='*60}\n")

    except Exception as exc:
        logger.error("[RECORDING] Write failed: %s\n%s", exc, traceback.format_exc())
        print(f"[RECORDING] FAILED: {exc}")
        return

    if not twilio_call_sid:
        return

    db = SessionLocal()
    try:
        call = db.query(Call).filter(
            Call.twilio_call_sid == twilio_call_sid
        ).first()

        if not call:
            logger.warning("[RECORDING] No DB call for sid=%s", twilio_call_sid)
            return

        end_time = datetime.utcnow()
        duration = max(
            0,
            int((end_time - call.start_time).total_seconds())
            if call.start_time
            else 0,
        )

        updated = update_call(
            db,
            workspace_id=call.workspace_id,
            call_id=call.id,
            data=CallUpdate(
                status="completed",
                recording_url=recording_path,
                end_time=end_time,
                duration=duration,
            ),
        )
        db.commit()
        db.refresh(updated)
        logger.info(
            "[WS] Call complete — sid=%s | duration=%ds | recording=%s",
            twilio_call_sid, duration, filename,
        )
        print(f"[WS] Call complete — duration={duration}s — {filename}")

    except Exception as exc:
        logger.error("[WS] Call record update failed: %s\n%s", exc, traceback.format_exc())
    finally:
        db.close()