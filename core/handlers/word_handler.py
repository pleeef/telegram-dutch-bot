from telegram import Update, ForceReply
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from config import AUTHORIZED_USERS
import logging, random


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


class WordHandler:
    def __init__(self, openai_client):
        self.openai = openai_client

    def get_command_handler(self):
        return CommandHandler("word", self.run)

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not is_authorized(user.id):
            await update.message.reply_text("Sorry, you don't have access to this bot.")
            logger.info(f"Unauthorized user {user.id} tried to use the bot.")
            return

        word_to_define = " ".join(context.args)
        if not word_to_define:
            word_to_define = 'nietbestaan'

        context.user_data['mode'] = 'word'

        prompt = f"""Give a detailed explanation of the Dutch word '{word_to_define}'. Include the following:
                1. A clear definition in English.
                2. At least two example sentences in natural Dutch (with English translations).
                3. A memory aid (mnemonic) or trick to help remember the word. Suggest associations for memorization from English.

                Format the answer clearly using section headers for each part.
                Do not use HTML tags or HTML formatting in your response."""

        try:
            response = self.openai.chat_completion(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful Dutch vocabulary assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.4,
                top_p=0.9
            )

            word_info = response.choices[0].message.content.strip()

            await update.message.reply_text(word_info,  parse_mode="Markdown", disable_web_page_preview=True)
            logger.info(f"User {update.effective_user.id} requested word definition for: {word_to_define}.")

        except Exception as e:
            logger.error(f"Error in word mode: {e}")
            await update.message.reply_text("An error occurred while generating the text. Try again.")
