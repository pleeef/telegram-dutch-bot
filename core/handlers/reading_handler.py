from telegram import Update, ForceReply
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from config import AUTHORIZED_USERS, VALID_LEVELS, VOICES
from core.utils import generate_random_date_str
import logging, random, datetime


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


class ReadingHandler:
    def __init__(self, openai_client):
        self.openai = openai_client

    def get_command_handler(self):
        return CommandHandler("reading", self.run)

    async def run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not is_authorized(user.id):
            await update.message.reply_text("Sorry, you don't have access to this bot.")
            logger.info(f"Unauthorized user {user.id} tried to use the bot.")
            return

        args = context.args
        context.user_data['mode'] = 'reading'

        level = 'B1' # Level by default
        topic = 'today' # Topic by default

        if args:
            # Check the first argument for level
            if args[0].upper() in VALID_LEVELS:
                level = args[0].upper()
                args = args[1:]
            
            # All that's left is the topic
            if args:
                topic = " ".join(args)

        context.user_data['reading'] = level

        random_date_str, random_year, current_year = generate_random_date_str()

        if topic == "today":
            if random_year <= current_year:
                # Real fact from history
                prompt = (
                    f"Schrijf een korte tekst (max 250 woorden) in het Nederlands op niveau {level} "
                    f"over een belangrijk historisch feit ergens in de wereld dat plaatsvond op {random_date_str} "
                    f"(dit kan overal plaatsvinden, bijvoorbeeld in Europa, Azië, Afrika, Amerika, enz.). "
                    f"of over een beroemd persoon die op deze dag is geboren of over een boek dat in het gekozen jaar is gepubliceerd. "
                    f"Gebruik duidelijke taal die geschikt is voor taalleerders."
                )
            else:
                # Fantastic future
                prompt = (
                    f"Schrijf een korte fantasierijke tekst (max 250 woorden) in het Nederlands op niveau {level} "
                    f"over een bijzonder of belangrijk toekomstig feit dat zal plaatsvinden op {random_date_str}. "
                    f"Verzin creatieve details, technologieën of gebeurtenissen die in die tijd zouden kunnen bestaan. "
                    f"Maak het verhaal boeiend maar eenvoudig genoeg voor taalleerders."
                )
        else:
            prompt = f"Schrijf een korte tekst (max 250 woorden) in het Nederlands op niveau {level} over het onderwerp '{topic}'."


        try:
            response = self.openai.chat_completion(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a Dutch reading comprehension assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7,
                top_p=0.95
            )

            reading_text = response.choices[0].message.content.strip()
        
            # Save the generated sentence
            context.user_data['reading_text'] = reading_text
            
            # Select a random voice
            selected_voice = random.choice(VOICES)

            # Generate an audio file using the OpenAI client
            audio_path = self.openai.generate_audio(reading_text, voice=selected_voice)

            # Sending an audio file
            await update.message.reply_audio(audio=open(audio_path, "rb"))
            await update.message.reply_text(f"Hier is een leestekst op niveau {level} over '{topic}':\n\n" + reading_text)
            logger.info(f"User {update.effective_user.id} started the reading level {level}.")

        except Exception as e:
            logger.error(f"Error in reading: {e}")
            await update.message.reply_text("An error occurred while generating the text. Try again.")
