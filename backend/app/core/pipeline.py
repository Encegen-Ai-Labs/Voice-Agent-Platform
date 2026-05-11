import audioop
import io
import os
from dataclasses import dataclass, field

from deepgram import DeepgramClient
from groq import Groq
import gtts
from pydub import AudioSegment


@dataclass
class AgentConfig:
    system_prompt: str = (
        "You are a helpful voice assistant. "
        "Keep responses concise and conversational, suitable for text-to-speech."
    )
    llm_model: str = "llama-3.3-70b-versatile"
    language: str = "en"


class VoicePipeline:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()

        deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")
        if not deepgram_key:
            raise ValueError("DEEPGRAM_API_KEY is not set in environment")
        if not groq_key:
            raise ValueError("GROQ_API_KEY is not set in environment")

        self._deepgram = DeepgramClient(api_key=deepgram_key)
        self._groq = Groq(api_key=groq_key)

    def _transcribe(self, audio_bytes: bytes) -> str:
        try:
            response = self._deepgram.listen.v1.media.transcribe_file(
                request=audio_bytes,
                model="nova-2",
                smart_format=True,
                language=self.config.language,
                encoding="mulaw",
                request_options={"additional_query_parameters": {"sample_rate": 8000}},
            )
            transcript = response.results.channels[0].alternatives[0].transcript
        except Exception as e:
            raise RuntimeError(f"STT failed: {e}") from e

        if not transcript.strip():
            raise ValueError("Deepgram returned an empty transcript")

        return transcript

    def _generate_response(self, transcript: str) -> str:
        try:
            completion = self._groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.config.system_prompt},
                    {"role": "user", "content": transcript},
                ],
                model=self.config.llm_model,
            )
            return completion.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"LLM failed: {e}") from e

    async def _synthesize(self, text: str) -> bytes:
        try:
            mp3_buf = io.BytesIO()
            gtts.gTTS(text=text, lang=self.config.language).write_to_fp(mp3_buf)
            mp3_bytes = mp3_buf.getvalue()

            audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
            audio = audio.set_frame_rate(8000).set_channels(1)

            pcm_buf = io.BytesIO()
            audio.export(pcm_buf, format="raw", codec="pcm_s16le")
            pcm_bytes = pcm_buf.getvalue()

            return audioop.lin2ulaw(pcm_bytes, 2)
        except Exception as e:
            raise RuntimeError(f"TTS failed: {e}") from e

    async def process_audio(self, audio_bytes: bytes) -> bytes:
        transcript = self._transcribe(audio_bytes)
        response_text = self._generate_response(transcript)
        audio_out = await self._synthesize(response_text)
        return audio_out
