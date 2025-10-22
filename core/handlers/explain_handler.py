from telegram import Update, ForceReply
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from config import AUTHORIZED_USERS
import logging, random


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


class ExplainHandler:
    def __init__(self, openai_client):
        self.openai = openai_client

    def get_command_handler(self):
        return CommandHandler("explain", self.run)

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not is_authorized(user.id):
            await update.message.reply_text("Sorry, you don't have access to this bot.")
            logger.info(f"Unauthorized user {user.id} tried to use the bot.")
            return

        sentence = " ".join(context.args)
        if not sentence:
            sentence = 'Waarom bestaat er überhaupt iets, en niet niets?'

        context.user_data['mode'] = 'explain'

        prompt = (
            f"Explain the Dutch grammar of the following sentence or rule: '{sentence}'. "
            "Write the explanation in clear and simple English, suitable for a language learner. "
            "Include examples in Dutch with translations to illustrate the rule. "
            "Focus on clarity and correctness. "
            "Do not use HTML tags or HTML formatting in your response."
        )

        try:
            response = self.openai.chat_completion(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful Dutch grammar assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.4,
                top_p=0.9
            )

            explanation = response.choices[0].message.content.strip()

            await update.message.reply_text(explanation, parse_mode="Markdown", disable_web_page_preview=True)
            logger.info(f"User {update.effective_user.id} requested grammar explanation for: {sentence}.")

        except Exception as e:
            logger.error(f"Error in explain mode: {e}")
            await update.message.reply_text("An error occurred while generating the text. Try again.")
