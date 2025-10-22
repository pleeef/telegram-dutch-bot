import openai, logging, tempfile
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
