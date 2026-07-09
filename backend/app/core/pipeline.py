import asyncio
import audioop
import io
import logging
import os
import time
import uuid as _uuid_module
from dataclasses import dataclass
from uuid import UUID
import base64
import json
import websockets

from groq import Groq
from pydub import AudioSegment
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


_SENTENCE_ENDS = {".", "!", "?"}
_MIN_CHUNK_WORDS = 12

_CARTESIA_DEFAULT_VOICE = "79a125e8-cd45-4c13-8a67-188112f4dd22"
_CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
_CARTESIA_AVAILABLE = bool(_CARTESIA_API_KEY)
print(
    f"CARTESIA AVAILABLE = {_CARTESIA_AVAILABLE}"
)


@dataclass
class AgentConfig:
    system_prompt: str = (
        "You are a friendly phone assistant. "
        "Reply in ONE complete, natural sentence — 10 to 15 words. "
        "Sound like a real human on a phone call, not a robot. "
        "Always finish the sentence completely — never stop mid-thought. "
        "Never greet or introduce yourself unless asked. "
        "No lists, no bullet points, no filler words like 'Certainly!' or 'Of course!'."
    )
    llm_model: str = "llama-3.1-8b-versatile"
    knowledge_context: str = ""
    language: str = "en"
    tts_voice: str = _CARTESIA_DEFAULT_VOICE
    tts_edge_voice: str = "en-US-AriaNeural"
    agent_id: UUID | None = None
    db: Session | None = None


class VoicePipeline:

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()

        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY is not set in environment")

        self._groq = Groq(api_key=groq_key)

        self.last_transcript: str | None = None
        print("=" * 80)
        print("CARTESIA_API_KEY:", bool(_CARTESIA_API_KEY))
        print("CARTESIA_AVAILABLE:", _CARTESIA_AVAILABLE)
        print("=" * 80)
        self.last_response: str | None = None

        # Persistent Cartesia WebSocket — avoids per-turn handshake (~200-400ms saved)
        self._cartesia_ws = None
        self._cartesia_ws_lock = asyncio.Lock()

    async def _get_cartesia_ws(self):
        """Return a live Cartesia WebSocket, reconnecting if closed."""
        async with self._cartesia_ws_lock:
            ws = self._cartesia_ws

            if ws is not None:
                try:
                    await ws.ping()
                    return ws
                except Exception:
                    self._cartesia_ws = None
            ws_url = "wss://api.cartesia.ai/tts/websocket"
            headers = {
                "X-API-Key": _CARTESIA_API_KEY,
                "Cartesia-Version": "2024-06-10",
            }
            connect_start = time.time()
            self._cartesia_ws = await websockets.connect(
                ws_url, additional_headers=headers
            )
            print(f"[PERF] Cartesia WS (re)connected in {time.time() - connect_start:.2f}s")
            return self._cartesia_ws

    async def close(self) -> None:
        """Close the persistent Cartesia WebSocket on call teardown."""
        if self._cartesia_ws is not None:
            try:
                await self._cartesia_ws.close()
            except Exception:
                pass
            self._cartesia_ws = None

 
    def _build_system_prompt(self) -> str:
        parts = [self.config.system_prompt]

        if self.config.knowledge_context:
            parts.append(
                f"\n\nKnowledge Base (use only if directly relevant):\n"
                f"{self.config.knowledge_context[:1500]}"
            )

        parts.append(
            "\n\nREMINDER: ONE complete natural sentence. 10-15 words. "
            "Finish the thought fully — never leave it hanging."
        )

        return "".join(parts)

    def _collect_full_response(
        self,
        transcript: str,
        conversation_history: list | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        if conversation_history:
            messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": transcript})

        try:
            completion = self._groq.chat.completions.create(
                messages=messages,
                model=self.config.llm_model,
                stream=False,
                max_tokens=35,
                temperature=0.15,
                stop=["\n", "  "],
            )
            return (completion.choices[0].message.content or "").strip()
        except Exception as exc:
            raise RuntimeError(f"Groq LLM failed: {exc}") from exc

    def _stream_llm_sentences(
        self,
        transcript: str,
        conversation_history: list | None = None,
    ):
        """Stream Groq tokens and yield complete sentences as they arrive.
        This lets TTS start on sentence 1 while LLM is still generating sentence 2+.
        """
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        if conversation_history:
            messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": transcript})

        try:
            stream = self._groq.chat.completions.create(
                messages=messages,
                model=self.config.llm_model,
                stream=True,
                max_tokens=35,
                temperature=0.15,
                stop=["\n", "  "],
            )
        except Exception as exc:
            raise RuntimeError(f"Groq LLM stream failed: {exc}") from exc

        buffer = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            buffer += delta
            # Yield a sentence as soon as we have a complete one
            for end_char in _SENTENCE_ENDS:
                idx = buffer.find(end_char)
                while idx != -1:
                    sentence = buffer[: idx + 1].strip()
                    buffer = buffer[idx + 1 :]
                    if len(sentence.split()) >= 4:
                        yield sentence
                    idx = buffer.find(end_char)

        # Yield any remaining text (no trailing punctuation)
        remainder = buffer.strip()
        if remainder and len(remainder.split()) >= 4:
            yield remainder

  
    def _split_into_natural_chunks(self, text: str) -> list[str]:
       
        text = text.strip()
        if not text:
            return []

        if len(text.split()) <= _MIN_CHUNK_WORDS:
            return [text]

        chunks: list[str] = []
        buffer = ""

        for char in text:
            buffer += char
            if char in _SENTENCE_ENDS:
                candidate = buffer.strip()
                word_count = len(candidate.split())
                if word_count >= 6:
                    chunks.append(candidate)
                    buffer = ""

        remainder = buffer.strip()
        if remainder:
            if chunks and len(remainder.split()) < 6:
                # Merge short orphan with previous chunk for smooth delivery
                chunks[-1] = chunks[-1].rstrip() + " " + remainder
            else:
                chunks.append(remainder)

        return chunks if chunks else [text]

    async def _synthesize_cartesia(self, text: str) -> bytes:
        tts_start = time.time()
        ws_url = "wss://api.cartesia.ai/tts/websocket"
        headers = {
            "X-API-Key": _CARTESIA_API_KEY,
            "Cartesia-Version": "2024-06-10",
        }

        request_payload = json.dumps({
            "model_id": "sonic-2",
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self.config.tts_voice,
            },
            "language": "en",
            "context_id": str(_uuid_module.uuid4()),
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 8000,   
            },
            "continue": False,
        })

        pcm_chunks: list[bytes] = []
        first_chunk_time = None

        try:
            connect_start = time.time()
            async with websockets.connect(ws_url, additional_headers=headers) as ws:
                await ws.send(request_payload)
                print(
                f"[PERF] Cartesia connect took "
                f"{time.time() - connect_start:.2f}s"
            )

                while True:
                    raw_msg = await ws.recv()
                    msg = json.loads(raw_msg)

                    msg_type = msg.get("type")

                    if msg_type == "chunk":
                        chunk_b64 = msg.get("data", "")

                        if chunk_b64:
                            pcm_chunk = base64.b64decode(chunk_b64)

                            if first_chunk_time is None:
                                first_chunk_time = time.time()
                                print(
                                    f"[PERF] First Cartesia chunk after "
                                    f"{first_chunk_time - tts_start:.2f}s"
                                )

                            pcm_chunks.append(pcm_chunk)

                        if msg.get("done", False):
                            break

                    elif msg_type == "done":
                        break

                    elif msg_type == "error":
                        raise RuntimeError(
                            f"Cartesia error {msg.get('status_code')}: "
                            f"{msg.get('message', msg)}"
                        )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Cartesia TTS failed: {exc}") from exc

        if not pcm_chunks:
            raise RuntimeError("Cartesia returned no audio chunks")
        
        print(
    f"[PERF] Cartesia took {time.time() - tts_start:.2f}s"
)

        raw_pcm = b"".join(pcm_chunks)
        return audioop.lin2ulaw(raw_pcm, 2)
    
    async def _synthesize_cartesia_stream(
        self,
        text: str,
    ):
        request_payload = json.dumps({
            "model_id": "sonic-2",
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self.config.tts_voice,
            },
            "language": "en",
            "context_id": str(_uuid_module.uuid4()),
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 8000,
            },
            "continue": False,
        })

        try:
            ws = await self._get_cartesia_ws()
            print(
                    f"[PERF] Cartesia request sent at "
                    f"{time.time():.3f}"
                )
            tts_start = time.time()
            await ws.send(request_payload)
            print(
                f"[PERF] Cartesia request sent "
                f"{time.time() - tts_start:.2f}s"
            )
            print(
                    f"[PERF] Waiting for first Cartesia chunk "
                    f"{time.time():.3f}"
                )

            first_cartesia_chunk = True

            while True:
                    raw_msg = await ws.recv()

                    if first_cartesia_chunk:
                        print(
                            f"[PERF] First Cartesia audio after "
                            f"{time.time() - tts_start:.2f}s"
                        )
                        first_cartesia_chunk = False
                    msg = json.loads(raw_msg)

                    msg_type = msg.get("type")

                    if msg_type == "chunk":
                        chunk_b64 = msg.get("data", "")

                        if chunk_b64:
                            pcm_chunk = base64.b64decode(chunk_b64)
                            mulaw_chunk = audioop.lin2ulaw(pcm_chunk, 2)

                            print(f"[STREAM] cartesia chunk {len(mulaw_chunk)} bytes")

                            for i in range(0, len(mulaw_chunk), 320):
                                yield mulaw_chunk[i:i + 320]

                        if msg.get("done", False):
                            break

                    elif msg_type == "done":
                        break

                    elif msg_type == "error":
                        raise RuntimeError(f"Cartesia error: {msg}")

        except Exception as exc:
            # Connection is dead — clear it so next call reconnects
            self._cartesia_ws = None
            raise RuntimeError(f"Cartesia stream failed: {exc}") from exc

    async def _synthesize_edge_fallback(self, text: str) -> bytes:
        """Edge TTS fallback — used only when CARTESIA_API_KEY is not set."""
        import edge_tts
        communicate = edge_tts.Communicate(
            text, self.config.tts_edge_voice, rate="-8%", pitch="-3Hz"
        )
        mp3_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])
        if not mp3_chunks:
            raise RuntimeError("Edge TTS returned no audio")
        mp3_data = b"".join(mp3_chunks)
        audio = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
        audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2)
        return audioop.lin2ulaw(audio.raw_data, 2)

    async def _synthesize(self, text: str) -> bytes:
       
        t0 = time.time()
        try:
            if _CARTESIA_AVAILABLE:
                audio = await self._synthesize_cartesia(text)
                logger.info("[TTS] Cartesia %.2fs | %r", time.time() - t0, text)
            else:
                logger.warning(
                    "[TTS] CARTESIA_API_KEY not set — falling back to Edge TTS. "
                    "Set CARTESIA_API_KEY in .env for production."
                )
                audio = await self._synthesize_edge_fallback(text)
                logger.info("[TTS] EdgeTTS %.2fs | %r", time.time() - t0, text)
            return audio
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if _CARTESIA_AVAILABLE:
                logger.error("[TTS] Cartesia error (%s) — trying Edge TTS fallback", exc)
                try:
                    return await self._synthesize_edge_fallback(text)
                except Exception as fe:
                    raise RuntimeError(f"Both TTS backends failed: {fe}") from fe
            raise RuntimeError(f"TTS failed: {exc}") from exc
        
    
    
    async def _synthesize_cartesia_stream_browser(self, text: str):
        """
        Streams raw PCM16 8kHz chunks directly from Cartesia using an isolated socket.
        """
        import websockets
        import uuid
        import os
        if not text.strip():
            return

        api_key = os.getenv("CARTESIA_API_KEY")
        headers = {
            "X-API-Key": api_key,
            "Cartesia-Version": "2024-06-10"
        }
        
        # 1. Generate a strict unique ID so Cartesia knows it's a new audio request
        context_id = str(uuid.uuid4())
        
        # 2. Use a completely fresh, isolated connection so previous turns don't pollute the socket
        try:
            async with websockets.connect("wss://api.cartesia.ai/tts/websocket", additional_headers=headers) as ws:
                request_payload = {
                    "context_id": context_id,
                    "model_id": "sonic-2",
                    "transcript": text,
                    "voice": {
                        "mode": "id",
                        "id": self.config.tts_voice,
                    },
                    "output_format": {
                        "container": "raw",
                        "encoding": "pcm_s16le",
                        "sample_rate": 8000,
                    },
                }
                
                await ws.send(json.dumps(request_payload))
                
                while True:
                    raw_msg = await ws.recv()
                    msg = json.loads(raw_msg)
                    
                    if "error" in msg:
                        print(f"\n❌ CARTESIA REJECTED AUDIO: {msg['error']}\n")
                        break
                        
                    chunk_b64 = msg.get("data")
                    if chunk_b64:
                        pcm_chunk = base64.b64decode(chunk_b64)
                        yield pcm_chunk
                        
                    if msg.get("done") or msg.get("type") == "done":
                        break
                        
        except Exception as exc:
            logger.error("[Pipeline] Isolated Cartesia stream failed: %s", exc)
    async def stream_audio_sentences(
        self,
        transcript: str,
        conversation_history: list | None = None,
    ):
      
        logger.info("[Pipeline] stream_audio_sentences ENTER")
        pending_tasks: list[tuple[asyncio.Task, str]] = []

        try:
            llm_start = time.time()

            full_response_parts = []
            first_sentence = True

            for sentence in self._stream_llm_sentences(
                transcript,
                conversation_history,
            ):
                full_response_parts.append(sentence)

                if first_sentence:
                    print(
                        f"[PERF] First sentence from Groq after "
                        f"{time.time() - llm_start:.2f}s"
                    )
                    first_sentence = False

                yield sentence, None

            full_response = " ".join(
                full_response_parts
            )

            self.last_transcript = transcript
            self.last_response = full_response

        except asyncio.CancelledError:
            for task, _ in pending_tasks:
                if not task.done():
                    task.cancel()
            if pending_tasks:
                await asyncio.gather(
                    *(t for t, _ in pending_tasks), return_exceptions=True
                )
            raise


    async def synthesize_sentence(self, sentence: str) -> bytes:
        return await self._synthesize(sentence)
    
    async def stream_sentence_audio(
        self,
        sentence: str,
    ):
        async for chunk in self._synthesize_cartesia_stream(
            sentence
        ):

            yield chunk

    async def process_transcript(
        self,
        transcript: str,
        conversation_history: list | None = None,
    ) -> bytes | None:
        transcript = transcript.strip()
        if not transcript:
            return None
        response_text = await asyncio.to_thread(
            self._collect_full_response, transcript, conversation_history
        )
        self.last_transcript = transcript
        self.last_response = response_text
        return await self._synthesize(response_text)

    def _generate_response_sync(
        self,
        transcript: str,
        conversation_history: list | None = None,
    ) -> str:
        """Alias kept for any external callers."""
        return self._collect_full_response(transcript, conversation_history)


def _is_valid_sentence(s: str) -> bool:
    cleaned = s.replace(".", "").replace("!", "").replace("?", "").strip()
    return len(cleaned) > 2