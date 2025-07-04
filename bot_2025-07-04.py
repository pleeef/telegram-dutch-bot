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

    # --- ИЗМЕНЕННЫЙ ТЕКСТ: Обновлено описание команды /translation ---
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
        " /translation [level] [style] [topic] — translate the text into Dutch\n"
        "   Style codes: A=Alice, N=Nabokov, F=Fantasy, T=Travel, L=Tearning\n\n"
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
    # --- НОВАЯ ЛОГИКА: Инициализация истории сообщений ---
    context.user_data['messages'] = [{"role": "system", "content": "You are a friendly and helpful Dutch language tutor. You engage in a free conversation with the user in Dutch. If the user makes a grammatical mistake, you correct it and explain the correction briefly and clearly in ENGLISH. Then you continue the conversation in Dutch."}]
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
    
    # --- НОВАЯ ЛОГИКА: Инициализация истории с системным сообщением ---
    context.user_data['messages'] = [{"role": "system", "content": f"You are a helpful language assistant guiding a role-playing game on the topic: '{context.user_data['roleplay_topic']}'. You correct the user's mistakes and explain them briefly in ENGLISH. You start the conversation."}]
    
    # ИЗМЕНЕННЫЙ PROMPT: Теперь он просто просит начать, а вся логика задана в system-сообщении
    prompt_start = f"Start the role-playing game in Dutch based on the topic: '{context.user_data['roleplay_topic']}'. Begin with a suitable sentence."

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=context.user_data['messages'] + [{"role": "user", "content": prompt_start}],
            max_tokens=150,
        )
        roleplay_start_text = response.choices[0].message.content.strip()
        # --- НОВАЯ ЛОГИКА: Добавляем ответ бота в историю ---
        context.user_data['messages'].append({"role": "assistant", "content": roleplay_start_text})
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
    
    # Этот prompt уже включает просьбу об объяснении на английском/русском
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
    """Запускает режим перевода, выдавая текст в заданном стиле."""
    if not is_authorized(update.effective_user.id): return

    # --- ИЗМЕНЕННЫЙ РАЗБОР АРГУМЕНТОВ ---
    args = context.args
    context.user_data.clear()
    context.user_data['mode'] = 'translation'
    
    level = 'B1' # Уровень по умолчанию
    style_code = 'L' # Стиль по умолчанию (Fantasy)
    topic = 'general' # Тема по умолчанию
    
    valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    valid_styles = ['A', 'N', 'F', 'T', 'L'] # A=Alice, N=Nabokov, F=Fantasy, T=Travel, L=Learning
    
    # Разбираем аргументы: [level] [style] [topic]
    if args:
        # Проверяем первый аргумент на уровень
        if args[0].upper() in valid_levels:
            level = args[0].upper()
            args = args[1:] # "Потребляем" аргумент уровня
        
        # Проверяем следующий аргумент на стиль
        if args and args[0].upper() in valid_styles:
            style_code = args[0].upper()
            args = args[1:] # "Потребляем" аргумент стиля
        
        # Всё, что осталось, это тема
        if args:
            topic = " ".join(args)

    context.user_data['translation_level'] = level
    context.user_data['translation_style'] = style_code
    
    # --- НОВАЯ ЛОГИКА: Словарь промптов для разных стилей ---
    prompts = {
    'A': (f"Generate a short, original text of three sentences in English in the style of Lewis Carroll's 'Through the Looking-Glass' (Alice in Wonderland part 2), suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    'N': (f"Generate a short, elegant English text of three sentences in the style of Vladimir Nabokov, suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    'F': (f"Generate a short, original text of three sentences in English in the style of a modern fairytale or a young adult fantasy book. The sentences should be suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    'T': (f"Generate a short, original text of three sentences in English that describes a place or an event, as if it comes from a traveler's journal. The sentences should have a vivid but clear writing style and be suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    'L': (f"Generate a short text of three sentences in English in a clear, simple style, like sentences found in a language learning textbook for level {level}. The sentences should focus on common vocabulary and straightforward grammar. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    }
    
    # Выбираем промпт из словаря. Если стиль не найден, используем 'F' (фэнтези) по умолчанию
    prompt = prompts.get(style_code, prompts['F'])

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful Dutch language teacher."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
        )
        text_to_translate = response.choices[0].message.content.strip()
        # Сохраняем ТЕКСТ для проверки (переименовано sentence -> text)
        context.user_data['text_to_translate'] = text_to_translate
        
        # --- ИЗМЕНЕННОЕ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ (zin -> text) ---
        await update.message.reply_text(
            f"Oké, laten we vertalen! Translate the following text into Dutch (level {level}, style: {style_code}, topic: '{topic}'):\n\n"
            f"**{text_to_translate}**"
        )
        logger.info(f"User {update.effective_user.id} started a translation task. Level: {level}, Style: {style_code}, Topic: {topic}.")
    except Exception as e:
        logger.error(f"Error in translation start: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

# --- Обработчик текстовых сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения в режиме /chat, /roleplay или /translation."""
    if not is_authorized(update.effective_user.id): return

    user_text = update.message.text
    mode = context.user_data.get('mode')

    # --- НОВАЯ ЛОГИКА ДЛЯ ДИАЛОГА (chat/roleplay) ---
    if mode == 'chat' or mode == 'roleplay':
        # Добавляем сообщение пользователя в историю
        context.user_data['messages'].append({"role": "user", "content": user_text})
        
        # Ограничиваем историю, чтобы она не была слишком длинной и дорогой
        max_history_length = 10 # 5 пар сообщений (user + bot) + system-prompt
        if len(context.user_data['messages']) > max_history_length:
            # Сохраняем system-prompt и последние N сообщений
            context.user_data['messages'] = [context.user_data['messages'][0]] + context.user_data['messages'][-max_history_length:]

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=context.user_data['messages'], # Передаем всю историю
                max_tokens=250,
            )
            reply_text = response.choices[0].message.content.strip()
            # Добавляем ответ бота в историю
            context.user_data['messages'].append({"role": "assistant", "content": reply_text})
            await update.message.reply_text(reply_text)
            logger.info(f"User {update.effective_user.id} sent a message in {mode} mode.")
        except Exception as e:
            logger.error(f"Error in handle_message for {mode} mode: {e}")
            await update.message.reply_text("An error occurred. Please try again.")

    # --- ИЗМЕНЕННЫЙ БЛОК ДЛЯ ПЕРЕВОДА (translation) ---
    elif mode == 'translation':
        # Переименовано sentence -> text
        original_text = context.user_data.get('text_to_translate', 'No text was provided.')
        
        # Сбрасываем режим после получения ответа
        context.user_data.clear()
        
        # --- ИЗМЕНЕННЫЙ PROMPT: Запрашивает короткий ответ и пояснения на английском ---
        prompt = (
            f"The original English text was: '{original_text}'. "
            f"The user provided this translation: '{user_text}'. "
            "Your task is to check the translation. "
            "1. First, provide the correct Dutch translation of the text. "
            "2. Then, provide a very brief and concise explanation of any errors in ENGLISH. "
            "Your entire answer must be short and direct. "
            "End your response with a sentence like: 'Try a new translation with /translation [level]!'."
        )

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful Dutch language teacher."},
                    {"role": "user", "content": prompt}
                ],
                # УВЕЛИЧЕН MAX_TOKENS для более полных, но не обрезанных ответов
                max_tokens=400,
            )
            reply_text = response.choices[0].message.content.strip()
            await update.message.reply_text(reply_text)
            logger.info(f"User {update.effective_user.id} sent a message in translation mode.")
        except Exception as e:
            logger.error(f"Error in handle_message for translation mode: {e}")
            await update.message.reply_text("An error occurred. Please try again.")

    else:
        # Если не в режиме, предлагает начать
        await update.message.reply_text(
            "To get started, use one of the commands: `/chat`, `/roleplay`, `/translation` etc."
        )
        return
        
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