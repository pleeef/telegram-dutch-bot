import openai
import logging
import tempfile
from pathlib import Path
from typing import Optional
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        openai.api_key = OPENAI_API_KEY
        self.client = openai

    def chat_completion(self, messages, model="gpt-4o", **kwargs):
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def generate_audio(self, text, voice="alloy"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmpfile:
            with self.client.audio.speech.with_streaming_response.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=text
            ) as response:
                response.stream_to_file(tmpfile.name)
            return tmpfile.name

    def transcribe_audio(self, audio_path: str, language: Optional[str] = None, model: str = "whisper-1") -> str:
        """Transcribe an audio file (Telegram voice is typically .ogg/opus).

        Returns plain text transcription.
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with path.open("rb") as f:
            kwargs = {}
            if language:
                kwargs["language"] = language

            # OpenAI audio transcription
            resp = self.client.audio.transcriptions.create(
                model=model,
                file=f,
                **kwargs,
            )

        # SDK returns an object with `.text` for transcription
        return getattr(resp, "text", str(resp)).strip()
