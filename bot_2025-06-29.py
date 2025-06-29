import logging
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
import re
import os

# Настройте логирование, чтобы видеть, что происходит с ботом
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Установите уровень логирования для библиотеки httpx, чтобы избежать лишних сообщений
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- ВАШИ API-КЛЮЧИ И НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AUTHORIZED_USERS_STR = os.environ.get("AUTHORIZED_USERS", "")
AUTHORIZED_USERS = [int(user_id) for user_id in AUTHORIZED_USERS_STR.split(',') if user_id]

# ------------------------------------

# Инициализируем клиента OpenAI
openai.api_key = OPENAI_API_KEY

# --- Проверка доступа ---
def is_authorized(user_id):
    """Проверяет, имеет ли пользователь право использовать бота."""
    return user_id in AUTHORIZED_USERS

# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при вызове /start."""
    user = update.effective_user
    # Проверяем, авторизован ли пользователь
    if not is_authorized(user.id):
        await update.message.reply_text(
            "Sorry, you don't have access to this bot."
        )
        logger.info(f"Unauthorized user {user.id} tried to use the bot.")
        return

    await update.message.reply_html(
        rf"Hoi, {user.mention_html()}! I'm your bot for learning Dutch. "
        "Here's what I can do:\n\n"
        "**Conversational practice:**\n"
        " /chat — free dialogue in Dutch\n"
        " /roleplay [topic] — role playing (for example, ` /roleplay in de winkel`)\n\n"
        "**Grammar:**\n"
        " /explain [sentence/rule] — grammar explanation\n\n"
        "**Reading:**\n"
        " /reading [level, topic] — short text with questions\n\n"
        "**Translation:**\n"
        " /translation [level, topic] — translate the sentence into Dutch\n\n"
        "**Dictionary:**\n"
        " /word [word] — definition, examples and synonyms\n\n"
        "Start with any command! 🇳🇱",
        reply_markup=ForceReply(selective=True),
    )
    logger.info(f"Authorized user {user.id} started the bot.")

# --- Команда /chat ---
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает свободный диалог."""
    if not is_authorized(update.effective_user.id): return
    
    # Сбрасываем старый режим и устанавливаем новый
    context.user_data.clear()
    context.user_data['mode'] = 'chat'
    await update.message.reply_text(
        "Oké, laten we praten! We kunnen over je dag praten of iets anders. Antwoord in het Nederlands, ik corrigeer je als het nodig is."
    )
    logger.info(f"User {update.effective_user.id} started a chat.")

# --- Команда /roleplay ---
async def roleplay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает отыгрывание роли."""
    if not is_authorized(update.effective_user.id): return

    args = context.args
    if not args:
        await update.message.reply_text("Please specify the topic. For example: `/roleplay in de winkel`")
        return
    
    # Сбрасываем старый режим и устанавливаем новый
    context.user_data.clear()
    context.user_data['mode'] = 'roleplay'
    context.user_data['roleplay_topic'] = " ".join(args)
    
    prompt = f"Je bent een AI-taalassistent die een rollenspel begeleidt. We gaan een rollenspel spelen over het onderwerp: '{context.user_data['roleplay_topic']}'. Jij begint. Begin met een passende zin. Ik ben de andere deelnemer en ik wil dat je me corrigeert als ik fouten maak in het Nederlands. Begin nu."

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful language learning assistant for Dutch."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
        )
        roleplay_start_text = response.choices[0].message.content.strip()
        await update.message.reply_text(f"Oké, laten we beginnen! We doen een rollenspel over '{context.user_data['roleplay_topic']}'.\n\n{roleplay_start_text}")
        logger.info(f"User {update.effective_user.id} started roleplay on topic: {context.user_data['roleplay_topic']}.")
    except Exception as e:
        logger.error(f"Error in roleplay: {e}")
        await update.message.reply_text("An error occurred while starting the role-playing game. Please try again.")

# --- Команда /explain ---
async def explain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Объясняет грамматику."""
    if not is_authorized(update.effective_user.id): return

    sentence = " ".join(context.args)
    if not sentence:
        await update.message.reply_text("Please write a sentence or rule to explain. For example: `/explain Het meisje heeft de hond.`")
        return

    # Сбрасываем режим
    context.user_data.clear()
    
    prompt = f"Leg de grammatica in het Nederlands van de volgende zin/regel uit: '{sentence}'. Leg het duidelijk uit, gebruik makkelijke woorden en geef indien mogelijk voorbeelden. Geef ook een korte en duidelijke uitleg in het Engels of Russisch erbij."

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful Dutch grammar assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
        )
        explanation = response.choices[0].message.content.strip()
        await update.message.reply_text(explanation)
        logger.info(f"User {update.effective_user.id} requested grammar explanation for: {sentence}.")
    except Exception as e:
        logger.error(f"Error in explain: {e}")
        await update.message.reply_text("There was an error explaining. Please try again.")

# --- Команда /reading ---
async def reading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Дает короткий текст для чтения."""
    if not is_authorized(update.effective_user.id): return

    args = context.args
    if not args:
        await update.message.reply_text("Please indicate the level (A1, A2, B1, B2, C1, C2) and topic. For example: `/reading A2 hobby's`")
        return
    
    # Сбрасываем режим
    context.user_data.clear()
    
    level = args[0].upper()
    topic = " ".join(args[1:]) if len(args) > 1 else "algemeen"
    
    valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    if level not in valid_levels:
        await update.message.reply_text("Invalid level. Please use A1, A2, B1, B2, C1 or C2.")
        return
        
    prompt = f"Schrijf een korte tekst (max 250 woorden) in het Nederlands op niveau {level} over het onderwerp '{topic}'."

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a Dutch reading comprehension assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
        )
        reading_text_with_questions = response.choices[0].message.content.strip()
        await update.message.reply_text(f"Hier is een leestekst op niveau {level} over '{topic}':\n\n" + reading_text_with_questions)
        logger.info(f"User {update.effective_user.id} requested a reading text: level {level}, topic {topic}.")
    except Exception as e:
        logger.error(f"Error in reading: {e}")
        await update.message.reply_text("An error occurred. Please try again.")
        
# --- Команда /word ---
async def word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Дает определение слова."""
    if not is_authorized(update.effective_user.id): return

    word_to_define = " ".join(context.args)
    if not word_to_define:
        await update.message.reply_text("Please write a word to define. For example: `/word gezellig`")
        return

    # Сбрасываем режим
    context.user_data.clear()

    prompt = f"Geef een gedetailleerde uitleg van het Nederlandse woord '{word_to_define}'. Geef de definitie, minimaal twee voorbeeldzinnen, en eventuele synoniemen of gerelateerde uitdrukkingen. Formatteer de antwoord duidelijk."

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful Dutch vocabulary assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
        )
        word_info = response.choices[0].message.content.strip()
        await update.message.reply_text(word_info)
        logger.info(f"User {update.effective_user.id} requested word definition for: {word_to_define}.")
    except Exception as e:
        logger.error(f"Error in word: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

# --- НОВАЯ КОМАНДА: /translation ---
async def translation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запускает режим перевода."""
    if not is_authorized(update.effective_user.id): return

    args = context.args
    # Сбрасываем старый режим и устанавливаем новый
    context.user_data.clear()
    context.user_data['mode'] = 'translation'
    
    level = 'B1' # Уровень по умолчанию
    topic = 'algemeen' # Тема по умолчанию
    
    valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    
    if args:
        # Пытаемся определить уровень из аргументов
        if args[0].upper() in valid_levels:
            level = args[0].upper()
            topic = " ".join(args[1:]) if len(args) > 1 else 'algemeen'
        else:
            # Если первый аргумент не уровень, считаем его темой
            topic = " ".join(args)

    context.user_data['translation_level'] = level
    
    #prompt = f"Geef mij één, niet te lange zin in het Engels op niveau {level} over het onderwerp '{topic}'. Deze zin moet ik vertalen naar het Nederlands. Geef alleen de zin, zonder extra uitleg."
    prompt = (
    f"Genereer een korte, originele tekst van drie zinnen in het Engels in de stijl van het boek 'Through the Looking-Glass' (Alice in Wonderland deel 2). "
    f"De tekst moet geschikt zijn voor vertaling naar niveau {level} Nederlands. "
    f"Geef alleen de zinnen, zonder extra uitleg of aanhalingstekens."
    )

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful Dutch language teacher."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
        )
        sentence_to_translate = response.choices[0].message.content.strip()
        # Сохраняем предложение для проверки
        context.user_data['sentence_to_translate'] = sentence_to_translate
        
        await update.message.reply_text(
            f"Oké, laten we vertalen! Vertaal de volgende zin naar het Nederlands (niveau {level}, onderwerp: '{topic}'):\n\n"
            f"**{sentence_to_translate}**"
        )
        logger.info(f"User {update.effective_user.id} started a translation task. Level: {level}, Topic: {topic}.")
    except Exception as e:
        logger.error(f"Error in translation start: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

# --- Обработчик текстовых сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения в режиме /chat, /roleplay или /translation."""
    if not is_authorized(update.effective_user.id): return

    user_text = update.message.text
    mode = context.user_data.get('mode')

    if mode == 'chat':
        # Prompt для чата
        prompt = f"De gebruiker heeft in het Nederlands geschreven: '{user_text}'. Je rol is om de gebruiker te corrigeren als hij fouten maakt, de correctie uit te leggen en een passend antwoord te geven. Antwoord in het Nederlands."
    elif mode == 'roleplay':
        # Prompt для ролевой игры
        topic = context.user_data.get('roleplay_topic', 'het rollenspel')
        prompt = f"We doen een rollenspel over '{topic}'. De gebruiker heeft gezegd: '{user_text}'. Geef een passend antwoord in het Nederlands en corrigeer eventuele grammaticale fouten van de gebruiker. Als er een fout is, leg dan uit waarom het fout is."
    elif mode == 'translation':
        # Prompt для проверки перевода
        original_sentence = context.user_data.get('sentence_to_translate', 'No sentence was provided.')
        
        # Сбрасываем режим после получения ответа
        context.user_data.clear()
        
        prompt = (
            f"De oorspronkelijke Engelse zin was: '{original_sentence}'. "
            f"De gebruiker heeft deze vertaling gegeven: '{user_text}'. "
            "Controleer de vertaling. Geef eerst de correcte Nederlandse vertaling. "
            "Als de gebruiker fouten heeft gemaakt, leg dan duidelijk uit welke fouten zijn gemaakt en hoe ze gecorrigeerd kunnen worden. "
            "Eindig met een zin zoals 'Probeer een nieuwe vertaling met /translation [niveau]!'. "
            "Antwoord in het Nederlands en formatteer het antwoord duidelijk."
        )

    else:
        # Если не в режиме, предлагает начать
        await update.message.reply_text(
            "To get started, use one of the commands: `/chat`, `/roleplay`, `/translation` и т.д. "
        )
        return
        
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful Dutch language teacher and speaking partner."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
        )
        reply_text = response.choices[0].message.content.strip()
        await update.message.reply_text(reply_text)
        logger.info(f"User {update.effective_user.id} sent a message in {mode} mode.")
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text("An error occurred. Please try again.")


# --- Основная функция для запуска бота ---
def main() -> None:
    """Запускает бота."""
    # Создаем Application и передаем токен
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("chat", chat))
    application.add_handler(CommandHandler("roleplay", roleplay))
    application.add_handler(CommandHandler("explain", explain))
    application.add_handler(CommandHandler("reading", reading))
    application.add_handler(CommandHandler("word", word))
    # ДОБАВЛЕНА НОВАЯ КОМАНДА
    application.add_handler(CommandHandler("translation", translation))
    
    # Обработчик для всех текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Бот запущен! Нажмите Ctrl+C, чтобы остановить.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()