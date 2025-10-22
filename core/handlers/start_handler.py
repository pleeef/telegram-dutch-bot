from telegram import Update, ForceReply
from telegram.ext import ContextTypes, CommandHandler
from config import AUTHORIZED_USERS
import logging

logger = logging.getLogger(__name__)

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS

class StartHandler:
    @staticmethod
    def get_handlers():
        return [
            CommandHandler("start", StartHandler.run_start),
            CommandHandler("info", StartHandler.run_info),
        ]

    @staticmethod
    async def run_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not is_authorized(user.id):
            await update.message.reply_text("Sorry, you don't have access to this bot.")
            logger.info(f"Unauthorized user {user.id} tried to use the bot.")
            return

        message = (
            "👋 Hoi! I'm your bot for learning Dutch.\n\n"
            "• /dictate — listen and write a sentence\n\n"
            "• /reading — short reading exercises\n"
            "• /translation — translate short texts\n"
            "• /explain [sentence/rule] — grammar explanation\n\n"
            "• /word — dictionary and examples\n\n"
            "For more info about a command, type `/info [command]`.\n"
            "Example: `/info translation`"
        )
        await update.message.reply_text(message)
        logger.info(f"Authorized user {user.id} started the bot.")

    @staticmethod
    async def run_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args
        if not args:
            await update.message.reply_text("Usage: /info [command]\nExample: /info reading")
            return

        command = args[0].lower()
        info_map = {
            "translation": (
                "📝 /translation [level] [style] [topic] — Generate a short English text to translate into Dutch.\n"
                "Styles:\n"
                "• A — *Alice* (playful, slightly absurd)\n"
                "• N — *Nabokov* (dry, minimal, surreal)\n"
                "• F — *Fantasy* (modern fairytale tone)\n"
                "• T — *Travel* (travel diary style)\n"
                "• L — *Learning* (textbook style, supports optional [topic])\n\n"
                "Examples:\n"
                "• `/translation B1 N`\n"
                "• `/translation B2 L food`"
            ),
            "reading": (
                "📖 /reading [level, topic] — Read a short Dutch text and listen to its audio version.\n"
                "If you use a regular topic (e.g. `/reading A2 love`), you'll get a story related to that theme.\n"
                "If you use the topic `today`, you'll receive a text about events that happened on this day, "
                "but set in a random year between 1700 and 2030 — and if the year is in the future, "
                "the AI will invent a plausible event for that time."
            ),
            "word": "📚 /word [word] — Get definition, examples, and synonyms.",
            "dictate": (
                "🎧 /dictate [level] — Listen to a Dutch sentence and write it down to practice listening and spelling.\n"
                "If you choose a normal level (A1-C2), you'll get everyday sentences.\n"
                "If you choose level N, you'll hear sentences containing numbers — for example, times, dates, prices, addresses, or phone numbers — "
                "covering topics like tijd, datums, geld, telefoonnummers, huisnummers, leeftijden, temperaturen, afstanden, and more."
            ),
            "explain": "🔤 /explain [sentence/rule] — Get a simple grammar explanation or clarification of a Dutch sentence.",
        }

        message = info_map.get(command, f"Unknown command: {command}")
        await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)
