from telegram.ext import Application
from config import TELEGRAM_TOKEN, MEMORY_FILE
from core.openai_client import OpenAIClient
from core.memory import MemoryManager
from core.handlers.start_handler import StartHandler
from core.handlers.translation_handler import TranslationHandler
from core.handlers.dictate_handler import DictateHandler
from core.handlers.reading_handler import ReadingHandler
from core.handlers.word_handler import WordHandler
from core.handlers.explain_handler import ExplainHandler

class BotApp:
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.memory = MemoryManager(MEMORY_FILE)
        self.openai = OpenAIClient()

        for handler in StartHandler.get_handlers():
            self.app.add_handler(handler)

        dictate_handler = DictateHandler(self.memory, self.openai)
        self.app.add_handler(dictate_handler.get_command_handler(), group=0)
        self.app.add_handler(dictate_handler.get_message_handler(), group=1)

        translation_handler = TranslationHandler(self.memory, self.openai)
        self.app.add_handler(translation_handler.get_command_handler(), group=0)
        self.app.add_handler(translation_handler.get_message_handler(), group=2)

        reading_handler = ReadingHandler(self.openai)
        self.app.add_handler(reading_handler.get_command_handler(), group=0)

        word_handler = WordHandler(self.openai)
        self.app.add_handler(word_handler.get_command_handler(), group=0)

        explain_handler = ExplainHandler(self.openai)
        self.app.add_handler(explain_handler.get_command_handler(), group=0)

    def run(self):
        print("Bot started...")
        self.app.run_polling()

if __name__ == "__main__":
    BotApp().run()
