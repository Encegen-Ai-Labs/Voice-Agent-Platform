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
from groq import Groq

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.pipeline import AgentConfig, VoicePipeline
from app.core.realtime_stt import RealtimeSTTClient
from app.core.call_prewarm import claim_prewarmed
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
    last_update_transcript = ""


    pipeline = VoicePipeline(AgentConfig())
    asyncio.create_task(
    pipeline._get_cartesia_ws()
)
    realtime_stt: RealtimeSTTClient | None = None

    stream_sid: str | None = None
    twilio_call_sid: str | None = None
    full_recording: bytearray = bytearray()       
      
    conversation_history: list[dict] = []
    full_conversation: list[dict] = []

    ai_speaking: bool = False
    response_started_at = 0.0
    interrupt_event: asyncio.Event = asyncio.Event()
    response_task: asyncio.Task | None = None
    last_processed_transcript: str = ""
    last_turn_id = None
    last_turn_transcript: str = ""
    pending_transcript: str | None = None  
    first_audio_time: float | None = None

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
        nonlocal first_audio_time
        nonlocal response_started_at
        nonlocal last_turn_transcript

        transcript = transcript.strip()
        if not transcript:
            return
        nonlocal last_update_transcript

        if event_type == "Update":
            if transcript == last_update_transcript:
                return

            last_update_transcript = transcript

        if (
            event_type == "StartOfTurn"
            and first_audio_time is not None
        ):
            print(
                f"[PERF] First audio -> StartOfTurn: "
                f"{time.time() - first_audio_time:.2f}s "
                f"(abs_first_audio={first_audio_time:.3f}, abs_now={time.time():.3f})"
            )
            # Reset so the NEXT utterance measures its own first-audio latency,
            # not elapsed time since the start of the whole call.
            first_audio_time = None

        print(f"[STT CALLBACK] [{event_type}] {transcript!r} | ai_speaking={ai_speaking} | stream_sid={stream_sid}")
        logger.info("[STT] [%s] %r", event_type, transcript)

        # ---- Interruption: user spoke while AI is talking ----
        if ( ai_speaking
            and event_type == "StartOfTurn"
            and (time.time() - response_started_at) > 1.0
        ):
            print("[WS] Barge-in detected — cancelling response task")
            logger.info("[WS] Barge-in detected — cancelling response task")
            print(
                f"[BARGE-IN] event={event_type} "
                f"elapsed={time.time()-response_started_at:.2f}s "
                f"text={transcript!r}"
            )
            await _cancel_response_task()
            interrupt_event.set()
            if stream_sid:
                try:
                    if not first_outbound_logged:
                        first_outbound_logged = True
                        print(
                            f"[PERF] First outbound audio to Twilio: {time.time():.3f}"
                        )
                    await websocket.send_json({
                        "event": "clear",
                        "streamSid": stream_sid,
                    })
                except Exception as exc:
                    logger.warning("[WS] Twilio clear failed: %s", exc)

        if event_type not in ("EndOfTurn", "EagerEndOfTurn"):
            return
        if event_type == "EndOfTurn":
            return
        print(
            f"[PERF] {event_type} received "
            f"at {time.time():.3f}"
        )

        last_update_transcript = ""

        if transcript == last_turn_transcript:
            print(
                f"[STT CALLBACK] Duplicate turn event skipped: "
                f"{transcript!r}"
            )
            return

        last_turn_transcript = transcript
        await asyncio.sleep(0.4)

        if transcript != last_turn_transcript:
            print(
                "[STT CALLBACK] Transcript changed, skipping stale turn"
            )
            return

        if transcript == last_processed_transcript:
            print(f"[STT CALLBACK] Duplicate transcript, skipping: {transcript!r}")
            return

        if response_task and not response_task.done():
            # The user has finished a NEW utterance while the AI is still
            # speaking a reply to an OLDER one. That older reply is now
            # stale — playing it out before starting the new one is what
            # caused the "wait through Hello's full audio" delay. Cancel
            # the stale response and answer the new turn immediately
            # instead of queuing behind it.
            print(f"[WS] New turn while AI speaking — cancelling stale response, answering: {transcript!r}")
            logger.info("[WS] New turn while AI speaking — cancelling stale response: %r", transcript)
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
            pending_transcript = None

        last_processed_transcript = transcript
        interrupt_event.clear()
        history_snapshot = list(conversation_history)

        print(
            f"[PERF] Launching response task "
            f"at {time.time():.3f}"
        )

        print(
            f"[WS] Launching response task "
            f"for: {transcript!r}"
        )

        async def run_response(turn_transcript: str, turn_history: list) -> None:
            nonlocal full_recording
            nonlocal ai_speaking, conversation_history, response_task
            nonlocal pending_transcript, last_processed_transcript
            nonlocal response_started_at

            ai_speaking = True
            response_started_at = time.time()
            assistant_parts: list[str] = []
            was_interrupted = False

            try:
                print(
                    f"[PERF] run_response entered "
                    f"at {time.time():.3f}"
                )
                print(f"[WS] run_response START: {turn_transcript!r} | stream_sid={stream_sid}")
                logger.info("[WS] run_response START: %r", turn_transcript)
                t0 = time.time()
                response_start = time.time()
                first_chunk_sent = False
                print(
                    f"[WS] Response started at "
                    f"{response_start}"
                )
                async for sentence, audio in pipeline.stream_audio_sentences(
                    turn_transcript, turn_history
                ):
                    if interrupt_event.is_set():
                        logger.info("[WS] Interrupt flag set — stopping audio")
                        was_interrupted = True
                        break

                    assistant_parts.append(sentence)
                    print(
                            f"[PERF] Starting stream_sentence_audio "
                            f"after {time.time() - response_start:.2f}s"
                        )

                    async for chunk in pipeline.stream_sentence_audio(
                        sentence
                    ):

                        if interrupt_event.is_set():
                            was_interrupted = True
                            break

                        full_recording.extend(chunk)

                        try:
                            if not first_chunk_sent:
                                first_chunk_sent = True

                                print(
                                    f"[PERF] First chunk sent to Twilio "
                                    f"after {time.time() - response_start:.2f}s"
                                )
                            await websocket.send_json({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": base64.b64encode(
                                        chunk
                                    ).decode()
                                },
                            })

                        except Exception as exc:
                            logger.error(
                                "[WS] Twilio send failed: %s",
                                exc,
                            )
                            return

                    if was_interrupted:
                        break

                if not was_interrupted and assistant_parts:
                    full_response = " ".join(assistant_parts)
                    pipeline.last_transcript = turn_transcript
                    pipeline.last_response = full_response

                    user_msg = {
                        "role": "user",
                        "content": turn_transcript,
                    }

                    assistant_msg = {
                        "role": "assistant",
                        "content": full_response,
                    }

                    conversation_history.append(user_msg)
                    conversation_history.append(assistant_msg)

                    full_conversation.append(user_msg)
                    full_conversation.append(assistant_msg)

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
                import traceback as _tb
                logger.error("[WS] run_response error: %s\n%s", exc, _tb.format_exc())
                print(f"[WS] run_response error: {exc}\n{_tb.format_exc()}")

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

    # NOTE: Realtime STT (Deepgram) initialization moved below, into the
    # "start" event handler inside next_media_chunk(). Twilio's wss:// query
    # string for the Media Stream is not a reliable way to receive call_id —
    # it can arrive as None even though it was correctly set in the URL.
    # The reliable mechanism is Twilio's <Parameter> tag, which arrives in
    # the "start" event's start.customParameters.call_id field. Since
    # Twilio always sends "start" before any "media" events, initializing
    # realtime_stt there (rather than here, before any events have
    # arrived) is safe and guarantees we have the correct call_id.

    
    async def next_media_chunk() -> bytes | object:
       
        nonlocal stream_sid
        nonlocal twilio_call_sid
        nonlocal call_id
        nonlocal realtime_stt
        nonlocal first_audio_time
        

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

            if event == "start":
                print(
                    f"[PERF] TWILIO START {time.time():.3f}"
                )

                start_data = data.get("start", {})
                stream_sid = data.get("streamSid") or start_data.get("streamSid")
                twilio_call_sid = (
                    data.get("callSid")
                    or start_data.get("callSid")
                )

                custom_params = start_data.get("customParameters", {}) or {}
                real_call_id = custom_params.get("call_id") or call_id
                call_id = real_call_id

                print(f"[WS] Stream started — resolved call_id={call_id!r}")

                try:
                    t0 = time.time()
                    realtime_stt = await claim_prewarmed(call_id)

                    if realtime_stt is not None:
                        realtime_stt._on_transcript = on_realtime_transcript
                        print(
                            f"[PERF] Reused pre-warmed Deepgram connection "
                            f"(lookup took {time.time() - t0:.3f}s)"
                        )
                    else:
                        realtime_stt = RealtimeSTTClient(
                            on_transcript=on_realtime_transcript
                        )
                        await realtime_stt.connect()

                except Exception as exc:
                    print(f"[WS] Realtime STT init failed: {exc!r}")

                _load_agent_config(twilio_call_sid, pipeline)

                return None

            elif event == "media":
                audio_chunk = base64.b64decode(data["media"]["payload"])
                nonlocal first_audio_time

                if first_audio_time is None:
                    first_audio_time = time.time()

                    print(
                        f"[PERF] TWILIO FIRST MEDIA "
                        f"{first_audio_time:.3f}"
                    )

                    print(
                        f"[PERF] First audio chunk "
                        f"at {first_audio_time:.3f}"
                    )

                    print(
                        f"[PERF] First audio from Twilio: "
                        f"{first_audio_time}"
                    )

                full_recording.extend(audio_chunk)

                if realtime_stt:
                    try:
                        if not hasattr(realtime_stt, "_first_audio_seen"):
                            realtime_stt._first_audio_seen = True
                            print(f"[PERF] First audio chunk received from Twilio: {time.time()}")
                            print(
                                f"[PERF] First audio sent to Deepgram at {time.time():.3f}"
                            )
                        
                        await realtime_stt.send_audio(audio_chunk)
                    except Exception as exc:
                        logger.error("[WS] STT send error: %s", exc)

                return audio_chunk

            # elif event == "start":
            #     print(f"[PERF] START EVENT {time.time()}")
            #     start_data = data.get("start", {})
            #     stream_sid = data.get("streamSid") or start_data.get("streamSid")
            #     twilio_call_sid = (
            #         data.get("callSid")
            #         or start_data.get("callSid")
            #     )

                # Pull call_id from Twilio's customParameters — the reliable
                # mechanism, unlike the wss:// URL query string which can
                # arrive as None. Fall back to whatever was in the URL
                # (call_id captured at function start) if customParameters
                # is somehow missing it, so nothing breaks either way.
                custom_params = start_data.get("customParameters", {}) or {}
                real_call_id = custom_params.get("call_id") or call_id
                call_id = real_call_id

                logger.info(
                    "[WS] Stream started sid=%s call_sid=%s call_id=%s",
                    stream_sid,
                    twilio_call_sid,
                    call_id,
                )
                print(f"[WS] Stream started — resolved call_id={call_id!r}")

                # Initialize Realtime STT now that we have the real call_id.
                # This runs once, here, before any "media" events can
                # possibly arrive (Twilio always sends "start" first).
                try:
                    t0 = time.time()
                    realtime_stt = await claim_prewarmed(call_id)

                    if realtime_stt is not None:
                        # Pre-warmed connection exists and is already
                        # connected — just attach the callback. Connect +
                        # silence warmup already happened in /incoming-call,
                        # in parallel with the <Say> greeting.
                        realtime_stt._on_transcript = on_realtime_transcript
                        print(
                            f"[PERF] Reused pre-warmed Deepgram connection "
                            f"(lookup took {time.time() - t0:.3f}s)"
                        )
                        logger.info(
                            "[WS] Reused pre-warmed Deepgram connection for call_id=%s",
                            call_id,
                        )
                    else:
                        print("[PERF] No pre-warmed Deepgram connection — falling back to fresh connect")
                        realtime_stt = RealtimeSTTClient(
                            on_transcript=on_realtime_transcript
                        )
                        print(f"[PERF] Deepgram startup took {time.time() - t0:.2f}s")
                        await realtime_stt.connect()
                        logger.info("[WS] Realtime STT Connected (fresh)")

                except Exception as exc:
                    print(f"[WS] Realtime STT init failed: {exc!r}")
                    import traceback as _tb
                    _tb.print_exc()
                    logger.error("[WS] Realtime STT init failed: %s", exc)

                _load_agent_config(twilio_call_sid, pipeline)
                if twilio_call_sid:
                    db = SessionLocal()

                    try:
                        call = db.query(Call).filter(
                            Call.twilio_call_sid == twilio_call_sid
                        ).first()

                        if call:
                            update_call(
                                db,
                                workspace_id=call.workspace_id,
                                call_id=call.id,
                                data=CallUpdate(
                                    status="ongoing"
                                ),
                            )

                    finally:
                        db.close()

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
        
        print(
            f"[RECORDING] Total bytes before save: {len(full_recording)}"
        )

        _save_recording(
            full_recording,
            twilio_call_sid,
            full_conversation,
        )


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
        pipeline.config.tts_voice = (
            agent.voice or AgentConfig.tts_voice
        )
        logger.info(
            "[WS] Voice selected: %s",
            pipeline.config.tts_voice,
        )
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

def detect_sentiment_ai(
    transcript: str,
) -> str:

    try:
        client = Groq(
            api_key=os.getenv("GROQ_API_KEY")
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": """
                You are a call-center QA analyst.

                Classify the FINAL customer sentiment at the end of the call.

                positive:
                - customer thanks the agent
                - issue appears resolved
                - customer expresses satisfaction
                - customer agrees the solution works

                negative:
                - customer is frustrated
                - issue unresolved
                - customer complains
                - customer is angry

                neutral:
                - no clear satisfaction or dissatisfaction

                Return ONLY:
                positive
                negative
                neutral
                """
                },
                {
                    "role": "user",
                    "content": transcript,
                },
            ],
        )

        sentiment = (
            response.choices[0]
            .message.content
            .strip()
            .lower()
        )

        if sentiment not in {
            "positive",
            "negative",
            "neutral",
        }:
            return "neutral"

        return sentiment

    except Exception:
        logger.exception(
            "[SENTIMENT] AI sentiment analysis failed"
        )
        return "neutral"
def _build_transcript(
    conversation: list[dict]
) -> str:

    lines = []

    for item in conversation:
        role = item.get("role")

        if role == "user":
            prefix = "USER"
        else:
            prefix = "AI"

        lines.append(
            f"{prefix}: {item.get('content', '')}"
        )

    return "\n".join(lines)

def _save_recording(
    recording: bytearray,
    twilio_call_sid: str | None,
    conversation: list[dict],
) -> None:

    if not recording:
        logger.warning("[RECORDING] No audio captured")
        return

    filename = (
        f"{twilio_call_sid}.wav"
        if twilio_call_sid
        else f"unknown_{int(time.time())}.wav"
    )

    try:
        recordings_dir = os.path.abspath("recordings")
        os.makedirs(recordings_dir, exist_ok=True)

        recording_path = os.path.join(
            recordings_dir,
            filename,
        )

        pcm_audio = audioop.ulaw2lin(
            bytes(recording),
            2,
        )

        with wave.open(recording_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(8000)
            wav_file.writeframes(pcm_audio)

        duration_s = len(pcm_audio) / (8000 * 2)

        print("\n" + "=" * 80)
        print(f"[RECORDING SAVED]")
        print(f"FILE      : {filename}")
        print(f"PATH      : {recording_path}")
        print(f"DURATION  : {duration_s:.1f}s")
        print(f"CALL SID  : {twilio_call_sid}")
        print("=" * 80 + "\n")

        logger.info(
            "[RECORDING] Saved %s (%0.1fs)",
            recording_path,
            duration_s,
        )

    except Exception as exc:
        logger.error(
            "[RECORDING] Write failed: %s\n%s",
            exc,
            traceback.format_exc(),
        )
        return

    # KEEP ALL THE EXISTING DB UPDATE CODE BELOW UNCHANGED

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
        transcript = _build_transcript(
            conversation
        )

        sentiment = detect_sentiment_ai(
            transcript,

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
                transcript=transcript,
                sentiment=sentiment,
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