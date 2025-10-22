from telegram import Update, ForceReply
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from config import AUTHORIZED_USERS, MEMORY_FILE, VALID_LEVELS, VOICES, NUMBERS
from core.utils import load_words_from_csv
from core.memory import MemoryManager
import logging, random


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


class DictateHandler:
    def __init__(self, memory, openai_client):
        self.memory = memory
        self.openai = openai_client

    def get_command_handler(self):
        return CommandHandler("dictate", self.run)
    
    def get_message_handler(self):
        # block=False ensures this handler won't stop other message handlers.
        return MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_dictate, block=False)

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not is_authorized(user.id):
            await update.message.reply_text("Sorry, you don't have access to this bot.")
            logger.info(f"Unauthorized user {user.id} tried to use the bot.")
            return

        args = context.args
        context.user_data['mode'] = 'dictate'
        # Set default level as B1
        if args:
            level = args[0].upper()
        else:
            level = 'B1'  

        if level not in VALID_LEVELS and level != 'N':
            level = 'B1'

        context.user_data['dictate_level'] = level

        recent_sentences = self.memory.get_recent_sentences(context.user_data['mode'])

        topics_n = random.choice(NUMBERS)

        if level != "N":
            prompt = f"""
                        Genereer twee eenvoudige zinnen voor het dictee Nederlands voor niveau {level}. 
                        ⚠️ Schrijf alleen de twee zinnen, elk op een nieuwe regel.
                        ⚠️ Gebruik geen inleidende tekst, geen nummers, geen extra uitleg.
                        De zinnen moeten vergelijkbaar zijn met die in de leerboeken voor dit niveau.
                        Vermijd herhaling van dezelfde thema's (bijvoorbeeld katten die slapen).
                        Gebruik afwisseling in onderwerpen: mensen, school, werk, reizen, eten, hobby's, enz.

                        Richtlijnen algemeen:
                        - Gebruik steeds verschillende werkwoorden in de zinnen (geen herhaling).
                        - Zorg voor variatie in onderwerpen: mensen, school, werk, reizen, eten, hobby's, natuur, enz.
                        - Kies regelmatig ook minder voor de hand liggende werkwoorden (bijv. bellen, brengen, zoeken, leren, wachten, spelen, kopen, schrijven, vergeten).
                        - Vermijd herhaling van dezelfde thema's (bijvoorbeeld steeds katten of koken).
                        
                        ➡️ Richtlijnen per niveau:
                        - Voor A2: gebruik korte en eenvoudige zinnen (6-10 woorden), in de tegenwoordige of toekomende tijd.
                        - Voor B1: gebruik zinnen van vergelijkbare lengte (8-12 woorden), maar voeg een kort nevenschikkend of onderschikkend voegwoord toe (zoals "omdat", "maar", "want", "daarom", "als"). 
                        Soms in de verleden tijd en met één of twee bijvoeglijke naamwoorden.
                        - Voor B2: gebruik complexere zinnen met bijzinnen, voegwoorden en meer details (12-18 woorden).
                        """
        else:
            prompt = f"""Je bent een taalcoach voor iemand die Nederlands leert (niveau A2-B1).
                            Genereer 2 korte, natuurlijke zinnen in gesproken Nederlands.
                            Elke zin moet **getallen bevatten** die iets uitdrukken dat te maken heeft met het volgende thema: {topics_n}.
                            Gebruik alledaagse situaties en eenvoudige woorden, geen formele of zeldzame taal.
                            Output alleen de twee zinnen in tekst, zonder vertaling of uitleg."""
        if recent_sentences:
            prompt += f"\n ⚠️ Do not repeat any of these sentences: {recent_sentences}"

        try:
            response = self.openai.chat_completion(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a useful assistant in creating educational materials."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.9,
                top_p=0.9,
                presence_penalty=0.5, 
                frequency_penalty=0.3
            )

            sentence_to_dictate = response.choices[0].message.content.strip()
        
            # Save the generated sentence
            context.user_data['dictation_text'] = sentence_to_dictate

            self.memory.add_sentence(context.user_data['mode'], sentence_to_dictate)
            
            # Select a random voice
            selected_voice = random.choice(VOICES)

            # Generate an audio file using the OpenAI client
            audio_path = self.openai.generate_audio(sentence_to_dictate, voice=selected_voice)

            # Sending an audio file
            await update.message.reply_audio(audio=open(audio_path, "rb"))
            logger.info(f"User {update.effective_user.id} started the dictation level {level}.")

        except Exception as e:
            logger.error(f"Error in dictate: {e}")
            await update.message.reply_text("An error occurred while generating the dictation. Try again.")


    async def check_dictate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверяет перевод, отправленный пользователем."""
        logger.info(f"DICTATE DEBUG — received update: {update}")
        user = update.effective_user

        mode = context.user_data.get("mode")
        if mode != "dictate":
            return

        user_text = update.message.text.strip()
        correct_text = context.user_data.get("dictation_text")

        if not correct_text:
            await update.message.reply_text("Please start with /dictate first.")
            return
        
        user_text_normalized = user_text.lower()
        correct_text_normalized = correct_text.lower()

        logger.info(f"check_dictate triggered, mode={mode}")

        logger.info(f"check_dictate triggered, mode={context.user_data.get('mode')}, text={update.message.text}")

        # Form a request to OpenAI for feedback
        try:
            feedback_prompt = (
                f"The original dictation text was: '{correct_text_normalized}'. "
                f"The user provided this written text based on the dictation: '{user_text_normalized}'. "
                f"First send the original dictation text to user. "
                f"Then your task is to compare two texts. "
                f"Check if the user's text is correct. If it is, respond with 'Correct!' "
                f"If it is incorrect, list all specific errors. Do not rewrite the sentence. Only list the differences. "
                f"Your entire answer must be short and direct. "
            )

            response = self.openai.chat_completion(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a dictation checker for Dutch language learning bot."},
                    {"role": "user", "content": feedback_prompt},
                ],
                max_tokens=400,
            )

            feedback = response.choices[0].message.content.strip()
            await update.message.reply_text(feedback, parse_mode="Markdown", disable_web_page_preview=True)

        except Exception as e:
            logger.error(f"Error in check_dictate: {e}")
            await update.message.reply_text("Sorry, something went wrong while checking your dictation.")
