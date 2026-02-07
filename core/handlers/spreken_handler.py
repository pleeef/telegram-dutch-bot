# core/handlers/spreken_handler.py
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from config import AUTHORIZED_USERS
from core.utils import (
    load_speaking_images_tasks,
    pick_random_task,
    image_abs_path,
    data_dir,
)
import asyncio
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


class SprekenHandler:
    def __init__(self, memory, openai_client):
        self.memory = memory
        self.openai = openai_client

    def get_command_handler(self):
        return CommandHandler("spreken", self.run)

    def get_message_handler(self):
        # block=False ensures this handler won't stop other message handlers.
        return MessageHandler(filters.VOICE, self.check_speaking, block=False)
    
    def get_secret_voice_handler(self):
        # block=False чтобы не мешать другим хэндлерам
        return MessageHandler(filters.VOICE, self.secret_voice_corrector, block=False)

    async def secret_voice_corrector(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not is_authorized(user.id):
            return

        # Если сейчас активен какой-то режим (например /spreken) — не вмешиваемся
        mode = context.user_data.get("mode")
        if mode == "spreken" and context.user_data.get("spreken_task"):
            return

        voice = update.message.voice
        if not voice:
            return

        await update.message.reply_text("✍️ Ik schrijf het uit…")

        tg_file = await context.bot.get_file(voice.file_id)
        tmp_path = data_dir() / f"tmp_secret_{user.id}.ogg"
        await tg_file.download_to_drive(custom_path=str(tmp_path))

        try:
            transcript = self.openai.transcribe_audio(str(tmp_path), language="nl").strip()
            corrected = await self._grammar_correct_nl(transcript)

            await update.message.reply_text(
                "ВАШ ответ:\n"
                f"{transcript}\n\n"
                "Корректный ответ:\n"
                f"{corrected}"
            )
        except Exception as e:
            logger.error(f"Error in secret voice corrector: {e}")
            await update.message.reply_text("Sorry, something went wrong while processing your voice.")
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass    
    
    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not is_authorized(user.id):
            await update.message.reply_text("Sorry, you don't have access to this bot.")
            logger.info(f"Unauthorized user {user.id} tried to use the bot.")
            return

        context.user_data["mode"] = "spreken"

        tasks = load_speaking_images_tasks()

        seen = set(context.user_data.get("spreken_seen_ids", []))
        task = pick_random_task(tasks, exclude_ids=seen)
        seen.add(str(task.get("id")))
        context.user_data["spreken_seen_ids"] = list(seen)

        prep_seconds = int(task.get("prep_seconds", 5))
        answer_seconds = int(task.get("answer_seconds", 20))

        context.user_data["spreken_task"] = {
            "id": str(task.get("id")),
            "question_nl": task.get("question_nl", ""),
            "answer_nl": task.get("answer_nl", ""),
            "prep_seconds": prep_seconds,
            "answer_seconds": answer_seconds,
            "deadline": time.time() + prep_seconds + answer_seconds,
        }

        img_path = image_abs_path(task)
        question_nl = task.get("question_nl", "")

        await update.message.reply_photo(
            photo=img_path.open("rb"),
            caption=(
                f"🗣️ Spreken (Deel 1)\n\n"
                f"{question_nl}\n\n"
                f"Je hebt {prep_seconds} sec om te kijken. Daarna: stuur een spraakbericht."
            ),
        )

        # After prep_seconds, send a "start speaking" prompt (without JobQueue dependency)
        context.application.create_task(
            self._send_prep_prompt_later(update.effective_chat.id, prep_seconds, context)
        )

        logger.info(
            f"User {user.id} started speaking task id={task.get('id')} prep={prep_seconds}s answer={answer_seconds}s"
        )

    async def _send_prep_prompt_later(self, chat_id: int, delay_seconds: int, context: ContextTypes.DEFAULT_TYPE):
        """Send the "begin speaking" prompt after a delay.

        We avoid PTB JobQueue to keep deployment simple.
        """
        try:
            await asyncio.sleep(max(0, int(delay_seconds)))
            await context.bot.send_message(
                chat_id=chat_id,
                text="🔔 Begin met spreken! Stuur je spraakbericht nu.",
            )
        except Exception as e:
            logger.error(f"Failed to send prep prompt: {e}")

    async def check_speaking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает voice-ответ для /spreken."""
        user = update.effective_user

        mode = context.user_data.get("mode")
        if mode != "spreken":
            return

        task = context.user_data.get("spreken_task")
        if not task:
            await update.message.reply_text("Start eerst met /spreken.")
            return

        if time.time() > task["deadline"]:
            await update.message.reply_text("⏱️ Tijd is voorbij. Probeer opnieuw: /spreken")
            return

        voice = update.message.voice
        if not voice:
            await update.message.reply_text("Stuur alsjeblieft een spraakbericht (voice).")
            return

        await update.message.reply_text("✅ Ontvangen. Ik schrijf het uit…")

        # 1) Download voice
        tg_file = await context.bot.get_file(voice.file_id)
        tmp_path = data_dir() / f"tmp_spreken_{user.id}.ogg"
        await tg_file.download_to_drive(custom_path=str(tmp_path))

        try:
            # 2) Transcript (дословно насколько возможно)
            transcript = await self._transcribe_voice(tmp_path)

            # 3) Corrected answer (только грамматика/орфография, без улучшения)
            corrected = await self._grammar_correct_nl(transcript)

            # 4) Possible answer (из JSON)
            possible = task.get("answer_nl", "")

            await update.message.reply_text(
                "ВАШ ответ:\n"
                f"{transcript}\n\n"
                "Корректный ответ:\n"
                f"{corrected}\n\n"
                "Возможный ответ:\n"
                f"{possible}"
            )
            context.user_data.pop("mode", None)
            context.user_data.pop("spreken_task", None)

        except Exception as e:
            logger.error(f"Error in speaking processing: {e}")
            await update.message.reply_text("Sorry, something went wrong while processing your voice.")
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    async def _transcribe_voice(self, audio_path: Path) -> str:
        """
        Точка адаптации под твой openai_client.
        Сделай тут так, как у тебя реализована транскрипция (Whisper / Audio API).
        """
        # Вариант A (если у тебя есть метод transcribe_audio):
        if hasattr(self.openai, "transcribe_audio"):
            return self.openai.transcribe_audio(str(audio_path), language="nl").strip()

        # Вариант B (если у тебя синхронный метод transcribe_audio):
        if hasattr(self.openai, "transcribe_audio_sync"):
            return self.openai.transcribe_audio_sync(str(audio_path), language="nl").strip()

        # Если пока нет — явно скажем, что нужно подключить:
        raise RuntimeError("No transcription method found in openai_client (expected transcribe_audio).")

    async def _grammar_correct_nl(self, text: str) -> str:
        """
        Исправляет только грамматику/орфографию/порядок слов.
        Не добавляет новых идей и не улучшает стиль.
        """
        prompt = (
            "Je bent een corrector Nederlands (NT2).\n"
            "Corrigeer alleen grammatica, spelling en woordvolgorde.\n"
            "Verander de inhoud niet: geen nieuwe informatie, geen extra zinnen, geen stijlverbetering.\n"
            "Houd het zo dicht mogelijk bij de originele tekst.\n"
            "Geef alleen de gecorrigeerde tekst terug, zonder uitleg."
        )

        response = self.openai.chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            max_tokens=200,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()