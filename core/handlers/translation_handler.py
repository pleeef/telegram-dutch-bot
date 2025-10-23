from telegram import Update, ForceReply
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from config import AUTHORIZED_USERS, WORDS_FILE, VALID_LEVELS, VALID_STYLES
from core.utils import load_words_from_csv
import logging
import random

logger = logging.getLogger(__name__)

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


class TranslationHandler:
    def __init__(self, memory, openai_client):
        self.memory = memory
        self.openai = openai_client

    def get_command_handler(self):
        return CommandHandler("translation", self.run)
    
    def get_message_handler(self):
        # block=False ensures this handler won't stop other message handlers.
        return MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_translation, block=False)


    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not is_authorized(user.id):
            await update.message.reply_text("Sorry, you don't have access to this bot.")
            logger.info(f"Unauthorized user {user.id} tried to use the bot.")
            return

        args = context.args
        context.user_data['mode'] = 'translation'
        
        level = 'B1' # Level by default
        style_code = 'L' # Style by default
        topic = 'general' # Topic by default
        
        # Split the arguments [level] [style] [topic]
        if args:
            # Check the first argument for level
            if args[0].upper() in VALID_LEVELS:
                level = args[0].upper()
                args = args[1:]
            
            # Check the next argument for style
            if args and args[0].upper() in VALID_STYLES:
                style_code = args[0].upper()
                args = args[1:]
            
            # All that's left is the topic
            if args:
                topic = " ".join(args)

        context.user_data['translation_level'] = level
        context.user_data['translation_style'] = style_code


        word_list = load_words_from_csv(WORDS_FILE)

        # Get 3 random words
        random_words = random.sample(word_list, 3)

        recent_sentences = self.memory.get_recent_sentences(context.user_data['mode'])
        

        prompts = {
            'A': (
                f"Write a short, simple text in English (three sentences), the vocabulary and grammar must strictly match level {level} for language learners. "
                f"The style should be playful and slightly absurd, similar to Lewis Carroll's 'Through the Looking-Glass', but simplified. "
                f"Use short sentences and avoid complex grammar or puns. "
                f"Each sentence must express the meaning of one of the following Dutch words: "
                f"'{random_words[0]}', '{random_words[1]}', '{random_words[2]}'. "
                f"Do not include the Dutch words themselves in the sentences. "
                f"Use only natural English words that match the meaning of each Dutch word. "
                f"Do not provide the translation of these words. No explanation, no quotation marks. Give only the sentences."
            ),
            'N': (
                f"Write a short, simple text in English (three sentences), the vocabulary and grammar must strictly match level {level} for language learners. "
                f"The style should resemble the absurd, minimal, and dry tone of Vladimir Nabokov's 'Invitation to a Beheading', but simplified. "
                f"Use short sentences and avoid complex grammar or puns. "
                f"Each sentence must express the meaning of one of the following Dutch words: "
                f"'{random_words[0]}', '{random_words[1]}', '{random_words[2]}'. "
                f"Do not include the Dutch words themselves in the sentences. "
                f"Use only natural English words that match the meaning of each Dutch word. "
                f"Do not provide the translation of these words. No explanation, no quotation marks. Give only the sentences."
            ),
            'F': (
                f"Write a short, simple text in English (three sentences), the vocabulary and grammar must strictly match level {level} for language learners. "
                f"The style of a modern fairytale or a young adult fantasy book. "
                f"Use short sentences and avoid complex grammar or puns. "
                f"Each sentence must express the meaning of one of the following Dutch words: "
                f"'{random_words[0]}', '{random_words[1]}', '{random_words[2]}'. "
                f"Do not include the Dutch words themselves in the sentences. "
                f"Use only natural English words that match the meaning of each Dutch word. "
                f"Do not provide the translation of these words. No explanation, no quotation marks. Give only the sentences."
            ),
            'T': (
                f"Write a short, simple text in English (three sentences), the vocabulary and grammar must strictly match level {level} for language learners. "
                f"The style that describes a place or an event, as if it comes from a traveler's journal. "
                f"Use short sentences and avoid complex grammar or puns. "
                f"Each sentence must express the meaning of one of the following Dutch words: "
                f"'{random_words[0]}', '{random_words[1]}', '{random_words[2]}'. "
                f"Do not include the Dutch words themselves in the sentences. "
                f"Use only natural English words that match the meaning of each Dutch word. "
                f"Do not provide the translation of these words. No explanation, no quotation marks. Give only the sentences."
            ),
            'L': (f"Generate a short text of three sentences in English in a clear, simple style, like sentences found in a language learning textbook for level {level}. The sentences should focus on common vocabulary and straightforward grammar. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
        }

        prompt = prompts.get(style_code, prompts['L']) # Default to Learning style for translation
        
        if recent_sentences:
            prompt += f"\n ⚠️ Do not repeat any of these sentences: {recent_sentences}"

        try:
            response = self.openai.chat_completion(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful Dutch language teacher."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.8,
                top_p=0.96
            )
            text_to_translate = response.choices[0].message.content.strip()
            context.user_data['text_to_translate'] = text_to_translate

            self.memory.add_sentence(context.user_data['mode'], text_to_translate)
            
            response = self.openai.chat_completion(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful Dutch language teacher."},
                    {"role": "user", "content": f"Give translation to English for this words: '{random_words[0]}', '{random_words[1]}', '{random_words[2]}'. use format:  '{random_words[0]}' - translation, '{random_words[1]}' - translation, '{random_words[2]}' - translation, that's all. "}
                ],
                max_tokens=50
            )
            words_translation = response.choices[0].message.content.strip()
            text_to_send= f"The words we are practicing are: {words_translation}.\n\n" + text_to_translate

            await update.message.reply_text(
                f"Oké, laten we vertalen! Translate the following text into Dutch (level {level}, style: {style_code}, topic: '{topic}'):\n\n"
                f"**{text_to_send}**"
            )
            logger.info(f"User {update.effective_user.id} started a translation task. Level: {level}, Style: {style_code}, Topic: {topic}.")
        except Exception as e:
            logger.error(f"Error in translation start: {e}")
            await update.message.reply_text("An error occurred. Please try again.")

    async def check_translation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверяет перевод, отправленный пользователем."""
        user = update.effective_user

        mode = context.user_data.get("mode")
        if mode != "translation":
            return

        user_translation = update.message.text.strip()
        original_text = context.user_data.get("text_to_translate")

        if not original_text:
            await update.message.reply_text("Please start with /translation first.")
            return

        # Form a request to OpenAI for feedback
        try:
            feedback_prompt = (
                    f"### TASK\n"
                    f"You are a friendly Dutch teacher. The student translated an English text into Dutch.\n"
                    f"Check their translation carefully and respond in the following format:\n\n"
                    f"✅ **Correct Dutch translation:** <your best natural Dutch version>\n"
                    f"💬 **Feedback (in English):** <brief explanation of any grammar or word choice issues>\n"
                    f"⭐ **Score:** <number from 1 to 10, based on meaning accuracy, grammar, and naturalness>\n\n"
                    f"### RULES\n"
                    f"- Do NOT skip any section.\n"
                    f"- The score must ALWAYS be included.\n"
                    f"- Do NOT write introductions or conclusions.\n"
                    f"- Be concise and friendly.\n\n"
                    f"### INPUT\n"
                    f"English text: {original_text}\n"
                    f"Student's Dutch translation: {user_translation}\n"
                )

            response = self.openai.chat_completion(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a friendly Dutch teacher."},
                    {"role": "user", "content": feedback_prompt},
                ],
                max_tokens=400,
                temperature=0.5,
            )

            feedback = response.choices[0].message.content.strip()
            await update.message.reply_text(feedback, parse_mode="Markdown", disable_web_page_preview=True)

        except Exception as e:
            logger.error(f"Error in check_translation: {e}")
            await update.message.reply_text("Sorry, something went wrong while checking your translation.")
