import logging
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
import re
import os
import random # Для выбора случайных предлогов/глаголов/слов по умолчанию
import string
import csv
import datetime

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

# Константы для режима /exam
# --- Константы для сообщений ---
MSG_NO_SKILL = "Please, provide skill: `/exam reading`, `/exam writing`, `/exam speaking` or `/exam culture`."
MSG_INVALID_SKILL = "Incorrect skill. Select one from: reading, writing, speaking, culture."
MSG_ERROR_OCCURRED = "Error occured. Please, Try again."
MSG_EXAM_TASK_TITLE = "📘 *{} task:*\n\n{}" # Используется для форматирования вывода
MSG_API_ERROR = "API Error: {}. Please, Try again."
MSG_EXAM_CONTEXT_ERROR = "Something went wrong with the exam task. Please try `/exam` again."
MSG_EXAM_FEEDBACK_TITLE = "📝 *Your answer to the task '{}' has been assessed:*\n\n{}"

# --- Константы для типов письменных заданий ---
WRITING_TYPES = ['brief', 'verslag', 'formulier invullen', 'klacht indienen']

# --- Список разрешенных навыков ---
ALLOWED_SKILLS = ['reading', 'writing', 'speaking', 'culture']

# Получаем путь к текущей директории, где находится bot.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Строим путь к файлу
csv_path = os.path.join(BASE_DIR, "frequent_words_2000_5000.csv")

# Читаем слова из CSV
def load_words_from_csv(path):
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        return [row[0] for row in reader if row]

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

    # --- ИЗМЕНЕННЫЙ ТЕКСТ: Обновлено описание команд ---
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
        "   Style codes: A=Alice, N=Nabokov, F=Fantasy, T=Travel, L=Learning\n\n"
        "**Practice:**\n"
        " /practice [level] [mode] [item] — specific practice (e.g., `/practice B1 prep in`)\n"
        "   Modes: `prep` (prepositions), `verb` (verbs), `word` (vocabulary)\n"
        "   Use `/more` to get more sentences in the current practice session.\n\n"
        "**Exam Preparation:**\n" # Новый раздел
        " /exam [skill] — get a A2-level exam task (e.g., `/exam writing`)\n"
        "   Skills: `reading`, `writing`, `speaking`, `culture`\n\n"
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
    
    context.user_data.clear() # Сбрасываем старый режим
    context.user_data['mode'] = 'chat'
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
    
    context.user_data.clear() # Сбрасываем старый режим
    context.user_data['mode'] = 'roleplay'
    context.user_data['roleplay_topic'] = " ".join(args)
    
    context.user_data['messages'] = [{"role": "system", "content": f"You are a helpful language assistant guiding a role-playing game on the topic: '{context.user_data['roleplay_topic']}'. You correct the user's mistakes and explain them briefly in ENGLISH. You start the conversation."}]
    
    prompt_start = f"Start the role-playing game in Dutch based on the topic: '{context.user_data['roleplay_topic']}'. Begin with a suitable sentence."

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=context.user_data['messages'] + [{"role": "user", "content": prompt_start}],
            max_tokens=150,
        )
        roleplay_start_text = response.choices[0].message.content.strip()
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

    context.user_data.clear() # Сбрасываем режим
    
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
    
    context.user_data.clear() # Сбрасываем режим
    
    level = args[0].upper()
    topic = " ".join(args[1:]) if len(args) > 1 else "algemeen"
    
    valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    if level not in valid_levels:
        await update.message.reply_text("Invalid level. Please use A1, A2, B1, B2, C1 or C2.")
        return
    
    today = datetime.date.today()

    # Случайный год от 500 до 2050
    random_year = random.randint(500, 2050)

    # Формируем строку даты
    random_date_str = today.strftime(f"%d %B {random_year}")

    if topic == "today":
        if random_year <= today.year:
            # Реальная история
            prompt = (
                f"Schrijf een korte tekst (max 250 woorden) in het Nederlands op niveau {level} "
                f"over een belangrijk historisch feit ergens in de wereld dat plaatsvond op {random_date_str} "
                f"(dit kan overal plaatsvinden, bijvoorbeeld in Europa, Azië, Afrika, Amerika, enz.). "
                f"Vertel wat er gebeurde en waarom het belangrijk was. "
                f"Gebruik duidelijke taal die geschikt is voor taalleerders."
            )
        else:
            # Фантастическое будущее
            prompt = (
                f"Schrijf een korte fantasierijke tekst (max 250 woorden) in het Nederlands op niveau {level} "
                f"over een bijzonder of belangrijk toekomstig feit dat zal plaatsvinden op {random_date_str}. "
                f"Verzin creatieve details, technologieën of gebeurtenissen die in die tijd zouden kunnen bestaan. "
                f"Maak het verhaal boeiend maar eenvoudig genoeg voor taalleerders."
            )
    else:
        prompt = f"Schrijf een korte tekst (max 250 woorden) in het Nederlands op niveau {level} over het onderwerp '{topic}'."

    # prompt = f"Schrijf een korte tekst (max 250 woorden) in het Nederlands op niveau {level} over het onderwerp '{topic}'."

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
        
# --- Команда /word (определение слова) ---
async def word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Дает определение слова."""
    if not is_authorized(update.effective_user.id): return

    word_to_define = " ".join(context.args)
    if not word_to_define:
        await update.message.reply_text("Please write a word to define. For example: `/word gezellig`")
        return

    context.user_data.clear() # Сбрасываем режим

    # prompt = f"Geef een gedetailleerde uitleg van het Nederlandse woord '{word_to_define}'. Geef de definitie, minimaal twee voorbeeldzinnen, en eventuele synoniemen of gerelateerde uitdrukkingen. Formatteer de antwoord duidelijk."
    prompt = f"""Give a detailed explanation of the Dutch word '{word_to_define}'. Include the following:
                    1. A clear definition in English.
                    2. At least two example sentences in natural Dutch (with English translations).
                    3. A memory aid (mnemonic) or trick to help remember the word. Suggest associations for memorization from English or Russian, depending on what is more suitable for this case.

                    Format the answer clearly using section headers for each part."""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful Dutch vocabulary assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
        )
        word_info = response.choices[0].message.content.strip()
        await update.message.reply_text(word_info)
        logger.info(f"User {update.effective_user.id} requested word definition for: {word_to_define}.")
    except Exception as e:
        logger.error(f"Error in word: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

# --- Команда /translation ---
async def translation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запускает режим перевода, выдавая текст в заданном стиле."""
    if not is_authorized(update.effective_user.id): return

    args = context.args
    context.user_data.clear() # Сбрасываем старый режим
    context.user_data['mode'] = 'translation'
    
    level = 'B1' # Уровень по умолчанию
    style_code = 'L' # Стиль по умолчанию (Learning)
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

    # def get_random_letter():
    #     excluded = {'Q', 'X', 'Y', 'Z', 'W'}
    #     allowed_letters = [letter for letter in string.ascii_uppercase if letter not in excluded]
    #     return random.choice(allowed_letters)

    # random_letter = get_random_letter()

    # Получаем список слов
    word_list = load_words_from_csv(csv_path)

    # Получаем 3 случайных слова
    random_words = random.sample(word_list, 3)

    
    # prompts = {
    #     #'A': (f"Generate a short, original text of three sentences in English in the style of Lewis Carroll's 'Through the Looking-Glass' (Alice in Wonderland part 2), suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    #     #'A': (f"Write a short, simple text in English (three sentences) using vocabulary and grammar at level {level}. The style should be playful and slightly absurd, similar to Lewis Carroll's 'Through the Looking-Glass', but simplified. Use short sentences and avoid complex grammar or puns. No explanation, no quotation marks. Give only the sentences."),
    #     'A': (f"Write a short, simple text in English (three sentences) using vocabulary and grammar at level {level}. The style should be playful and slightly absurd, similar to Lewis Carroll's 'Through the Looking-Glass', but simplified. Use short sentences and avoid complex grammar or puns. The **subject** (the main noun or character in each sentence) must begin with the letter '{random_letter}'. Other words can start with any letter. Avoid using alliteration. Try not to use the verb 'to dance'. No explanation, no quotation marks. Give only the sentences."),
    #     #'N': (f"Generate a short, original text of three sentences in English in the style of Vladimir Nabokov's 'Invitation to a Beheading', suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    #     'N': (f"Write a short, simple text in English (three sentences) using only {level}-level vocabulary and grammar. The style should resemble the absurd, minimal, and dry tone of Vladimir Nabokov's 'Invitation to a Beheading' (not poetic). Avoid metaphors. The **subject** (the main noun or character in each sentence) must begin with the letter '{random_letter}'. Other words can start with any letter. Avoid using alliteration. No explanation, no quotation marks. Give only the sentences."),
    #     'F': (f"Generate a short, original text of three sentences in English in the style of a modern fairytale or a young adult fantasy book. The sentences should be suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    #     'T': (f"Generate a short, original text of three sentences in English that describes a place or an event, as if it comes from a traveler's journal. The sentences should have a vivid but clear writing style and be suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    #     'L': (f"Generate a short text of three sentences in English in a clear, simple style, like sentences found in a language learning textbook for level {level}. The sentences should focus on common vocabulary and straightforward grammar. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    # }
    prompts = {
        'A': (
            f"Write a short, simple text in English (three sentences), the vocabulary and grammar must strictly match level {level} for language learners. "
            f"The style should be playful and slightly absurd, similar to Lewis Carroll's 'Through the Looking-Glass', but simplified. "
            f"Use short sentences and avoid complex grammar or puns. "
            f"Each sentence must express the meaning of one of the following Dutch words: "
            f"'{random_words[0]}', '{random_words[1]}', '{random_words[2]}'. "
            f"Do not include the Dutch words themselves in the sentences. "
            f"Use only natural English words that match the meaning of each Dutch word."
            f"Do not provide the translation of these words. No explanation, no quotation marks. Give only the sentences."
        ),
        'N': (
            f"Write a short, simple text in English (three sentences), the vocabulary and grammar must strictly match level {level} for language learners. "
            f"The style should resemble the absurd, minimal, and dry tone of Vladimir Nabokov's 'Invitation to a Beheading', but simplified. "
            f"Use short sentences and avoid complex grammar or puns. "
            f"Each sentence must express the meaning of one of the following Dutch words: "
            f"'{random_words[0]}', '{random_words[1]}', '{random_words[2]}'. "
            f"Do not include the Dutch words themselves in the sentences. "
            f"Use only natural English words that match the meaning of each Dutch word."
            f"Do not provide the translation of these words. No explanation, no quotation marks. Give only the sentences."
        ),
        'F': (
            f"Write a short, simple text in English (three sentences), the vocabulary and grammar must strictly match level {level} for language learners. "
            f"The style of a modern fairytale or a young adult fantasy book. "
            f"Use short sentences and avoid complex grammar or puns. "
            f"Each sentence must express the meaning of one of the following Dutch words: "
            f"'{random_words[0]}', '{random_words[1]}', '{random_words[2]}'. "
            f"Do not include the Dutch words themselves in the sentences. "
            f"Use only natural English words that match the meaning of each Dutch word."
            f"Do not provide the translation of these words. No explanation, no quotation marks. Give only the sentences."
        ),
        'T': (
            f"Write a short, simple text in English (three sentences), the vocabulary and grammar must strictly match level {level} for language learners. "
            f"The style that describes a place or an event, as if it comes from a traveler's journal. "
            f"Use short sentences and avoid complex grammar or puns. "
            f"Each sentence must express the meaning of one of the following Dutch words: "
            f"'{random_words[0]}', '{random_words[1]}', '{random_words[2]}'. "
            f"Do not include the Dutch words themselves in the sentences. "
            f"Use only natural English words that match the meaning of each Dutch word."
            f"Do not provide the translation of these words. No explanation, no quotation marks. Give only the sentences."
        ),
        'L': (f"Generate a short text of three sentences in English in a clear, simple style, like sentences found in a language learning textbook for level {level}. The sentences should focus on common vocabulary and straightforward grammar. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
    }

    prompt = prompts.get(style_code, prompts['L']) # Default to Learning style for translation

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
        context.user_data['text_to_translate'] = text_to_translate
        
        await update.message.reply_text(
            f"Oké, laten we vertalen! Translate the following text into Dutch (level {level}, style: {style_code}, topic: '{topic}'):\n\n"
            f"**{text_to_translate}**"
        )
        logger.info(f"User {update.effective_user.id} started a translation task. Level: {level}, Style: {style_code}, Topic: {topic}.")
    except Exception as e:
        logger.error(f"Error in translation start: {e}")
        await update.message.reply_text("An error occurred. Please try again.")

# --- НОВАЯ КОМАНДА: /practice ---
async def practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запускает режим тренировки предлогов, глаголов или слов."""
    if not is_authorized(update.effective_user.id): return

    args = context.args
    context.user_data.clear() # Сбрасываем старый режим
    context.user_data['mode'] = 'practice'

    level = 'B2' # Уровень по умолчанию
    sub_mode = 'prep' # Режим по умолчанию
    item = 'aan' # Предлог по умолчанию

    valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    valid_sub_modes = ['prep', 'verb', 'word']

    # Разбираем аргументы: [level] [sub_mode] [item]
    # Пример: /practice B1 prep in
    # Пример: /practice verb
    # if not args:
    #     await update.message.reply_text("Please specify the practice mode (prep, verb, word). Example: `/practice prep` or `/practice B1 verb gaan`")
    #     return
    if args:
    # Попытка определить уровень как первый аргумент
        if args[0].upper() in valid_levels:
            level = args[0].upper()
            args = args[1:] # Потребляем уровень
        
        # Попытка определить подрежим как следующий аргумент
        if args and args[0].lower() in valid_sub_modes:
            sub_mode = args[0].lower()
            args = args[1:] # Потребляем подрежим
        else:
            await update.message.reply_text(f"Invalid practice mode. Please use one of: {', '.join(valid_sub_modes)}. Example: `/practice prep`")
            return

        # Всё, что осталось, это элемент для тренировки
        if args:
            item = " ".join(args)

    context.user_data['practice_level'] = level
    context.user_data['practice_sub_mode'] = sub_mode
    context.user_data['practice_item'] = item # Сохраняем элемент для /more

    initial_system_message = {
        "role": "system",
        "content": f"You are a Dutch language tutor focused on '{sub_mode}' practice. You will provide three distinct English sentences for translation. After the user provides their translation, you will correct it and give a brief, concise explanation of any errors in ENGLISH. Then you will indicate that the user can type '/more' for more sentences. Maintain context about the item being practiced."
    }
    context.user_data['messages'] = [initial_system_message]

    prompt_templates = {
        'prep': f"Generate three distinct English sentences (each 5-10 words) for Dutch translation practice, focusing on the preposition '{item if item else 'a common Dutch preposition for level ' + level}'. Each sentence should demonstrate a different common usage (e.g., time, location, direction) if possible. Do not provide the translation. Just the three sentences, each on a new line.",
        'verb': f"Generate three distinct English sentences (each 5-10 words) for Dutch translation practice, focusing on the verb '{item if item else 'a common Dutch verb for level ' + level}'. Each sentence should demonstrate its usage with different pronouns and tenses (present, past) if possible. Do not provide the translation. Just the three sentences, each on a new line.",
        'word': f"Generate three distinct English sentences (each 5-10 words) for Dutch translation practice, focusing on the word '{item if item else 'a common Dutch word for level ' + level}'. Each sentence should demonstrate a different context or nuance if possible. Do not provide the translation. Just the three sentences, each on a new line.",
    }

    initial_prompt = prompt_templates.get(sub_mode)
    if not initial_prompt:
        await update.message.reply_text("Error: Could not find prompt for this practice mode.")
        return

    try:
        # Если элемент не был указан, просим AI выбрать его и вставить в промпт
        if not item:
            # Отдельный запрос для выбора элемента, если его нет
            selection_prompt = f"Suggest a very common Dutch {sub_mode} for level {level} to practice. Provide only the {sub_mode} itself, no extra text."
            selection_response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "You are a helpful language assistant."}, {"role": "user", "content": selection_prompt}],
                max_tokens=10,
            )
            item = selection_response.choices[0].message.content.strip()
            # Обновляем сохраненный элемент
            context.user_data['practice_item'] = item
            # Теперь используем выбранный AI элемент в основном промпте
            initial_prompt = prompt_templates.get(sub_mode).format(item=item, level=level)


        context.user_data['messages'].append({"role": "user", "content": initial_prompt})

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=context.user_data['messages'],
            max_tokens=200,
        )
        sentences_to_translate = response.choices[0].message.content.strip()
        context.user_data['current_practice_sentences'] = sentences_to_translate # Сохраняем предложения для проверки
        context.user_data['messages'].append({"role": "assistant", "content": sentences_to_translate}) # Добавляем в историю

        await update.message.reply_text(
            f"Oké, laten we {sub_mode}-training doen! Level: {level}" + (f", item: '{item}'" if item else "") + f"\n\nTranslate the following sentences into Dutch:\n\n**{sentences_to_translate}**"
        )
        logger.info(f"User {update.effective_user.id} started practice: {sub_mode}, item: {item}, level: {level}.")
    except Exception as e:
        logger.error(f"Error in practice start: {e}")
        await update.message.reply_text("An error occurred while starting the practice. Please try again.")

# --- НОВАЯ КОМАНДА: /more ---
async def more(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Генерирует новую порцию предложений для текущей тренировки."""
    if not is_authorized(update.effective_user.id): return

    mode = context.user_data.get('mode')
    if mode != 'practice':
        await update.message.reply_text("You are not in a practice session. Start one with `/practice [mode] [item]`.")
        return

    sub_mode = context.user_data.get('practice_sub_mode')
    item = context.user_data.get('practice_item')
    level = context.user_data.get('practice_level')

    if not sub_mode:
        await update.message.reply_text("It seems your practice session context is lost. Please start a new one with `/practice [mode] [item]`.")
        return
    
    # Промпт для генерации новой порции предложений (повторяем логику из practice)
    prompt_templates = {
        'prep': f"Generate three *new and different* English sentences (each 5-10 words) for Dutch translation practice, focusing on the preposition '{item if item else 'a common Dutch preposition for level ' + level}'. Each sentence should demonstrate a different common usage (e.g., time, location, direction) if possible. Do not provide the translation. Just the three sentences, each on a new line.",
        'verb': f"Generate three *new and different* English sentences (each 5-10 words) for Dutch translation practice, focusing on the verb '{item if item else 'a common Dutch verb for level ' + level}'. Each sentence should demonstrate its usage with different pronouns and tenses (present, past) if possible. Do not provide the translation. Just the three sentences, each on a new line.",
        'word': f"Generate three *new and different* English sentences (each 5-10 words) for Dutch translation practice, focusing on the word '{item if item else 'a common Dutch word for level ' + level}'. Each sentence should demonstrate a different context or nuance if possible. Do not provide the translation. Just the three sentences, each on a new line.",
    }
    next_prompt = prompt_templates.get(sub_mode)

    try:
        # Добавляем запрос пользователя для продолжения к истории
        context.user_data['messages'].append({"role": "user", "content": f"Please generate three more distinct English sentences for {sub_mode} practice related to '{item}' at level {level}. Do not provide translation."})

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=context.user_data['messages'], # Отправляем всю историю
            max_tokens=200,
        )
        sentences_to_translate = response.choices[0].message.content.strip()
        context.user_data['current_practice_sentences'] = sentences_to_translate # Сохраняем новые предложения
        context.user_data['messages'].append({"role": "assistant", "content": sentences_to_translate}) # Добавляем в историю

        await update.message.reply_text(
            f"Here are {sub_mode} practice sentences (level {level}" + (f", item: '{item}'" if item else "") + f"):\n\n**{sentences_to_translate}**"
        )
        logger.info(f"User {update.effective_user.id} requested more sentences for {sub_mode} practice, item: {item}.")
    except Exception as e:
        logger.error(f"Error in /more command: {e}")
        await update.message.reply_text("An error occurred while getting more practice sentences. Please try again or start a new practice.")


# --- НОВАЯ КОМАНДА: /exam ---
async def exam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Предоставляет пример экзаменационного задания A2 уровня."""
    if not is_authorized(update.effective_user.id): return

    if not context.args:
        await update.message.reply_text(MSG_NO_SKILL)
        return

    skill = context.args[0].lower()
    if skill not in ALLOWED_SKILLS:
        await update.message.reply_text(MSG_INVALID_SKILL)
        return

    # Очищаем все предыдущие данные пользователя, чтобы начать новое задание
    context.user_data.clear()

    prompt = ""
    role = ""
    writing_task_type = random.choice(WRITING_TYPES) # Выбираем тип для письменного задания

    # Создаем prompt в зависимости от навыка
    if skill == 'writing':
        prompt = (
            f"Geef een realistische oefenopdracht voor het onderdeel 'schrijven' van het NT2 Staatsexamen A2-niveau. "
            f"Het type opdracht moet zijn: '{writing_task_type}'. "
            f"Schrijf de opdracht duidelijk in het Nederlands. "
            "Gebruik moderne en relevante context. "
            "Geef alleen de opdracht, geen voorbeeldantwoord."
        )
        role = "You are an NT2 writing exam trainer."
    elif skill == 'reading':
        prompt = (
            "Geef een oefenopdracht voor het onderdeel 'lezen' op A2-niveau van het Staatsexamen NT2. "
            "Gebruik een korte tekst (maximaal 100 woorden) met 1-2 meerkeuzevragen. "
            "De context moet actueel of praktisch zijn (zoals werk, gemeente, school)."
            "Geef alleen de opdracht, geen voorbeeldantwoord."
        )
        role = "You are an NT2 reading exam trainer."
    elif skill == 'speaking':
        prompt = (
            "Geef een oefenopdracht voor het onderdeel 'spreken' op A2-niveau van het Staatsexamen NT2. "
            "Gebruik een realistische situatie (bijvoorbeeld werk, winkel, buren). "
            "Beschrijf wat de kandidaat moet zeggen of reageren."
            "Geef alleen de opdracht, geen voorbeeldantwoord."
        )
        role = "You are an NT2 speaking exam trainer."
    elif skill == 'culture':
        prompt = (
            # "Geef een korte cultuurquiz of vraag over de Nederlandse samenleving, wetten of gewoonten, geschikt voor iemand die zich voorbereidt op het inburgeringsexamen of NT2-examen op B1-niveau."
            # "Geef alleen de vraag, geen antwoord."
            "Geef een korte cultuurquizvraag over de Nederlandse samenleving, wetten of gewoonten, "
            "geschikt voor iemand die zich voorbereidt op het inburgeringsexamen of NT2-examen op A2-niveau. "
            "De vraag moet vergezeld gaan van vier (4) meerkeuzeopties (A, B, C, D). "
            "Geef alleen de vraag en de opties, ZONDER het juiste antwoord te markeren of te vermelden. "
            "Formateer de opties duidelijk, bijvoorbeeld: 'A) Optie 1\\nB) Optie 2'."
        )
        role = "You are a Dutch integration exam trainer."

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": role},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
        )
        exam_task = response.choices[0].message.content.strip()

        # --- Сохраняем контекст для handle_message ---
        context.user_data['mode'] = 'exam' # Устанавливаем режим 'exam'
        context.user_data['exam_skill'] = skill # Сохраняем выбранный навык
        context.user_data['exam_task'] = exam_task # Сохраняем текст сгенерированного задания
        # --- Конец сохранения контекста ---

        await update.message.reply_text(MSG_EXAM_TASK_TITLE.format(skill.capitalize(), exam_task), parse_mode="Markdown")
        logger.info(f"User {update.effective_user.id} requested exam task for: {skill}.")
    except openai.APIError as e:
        logger.error(f"OpenAI API Error in /exam: {e}")
        await update.message.reply_text(MSG_API_ERROR.format(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred in /exam: {e}")
        await update.message.reply_text(MSG_ERROR_OCCURRED)


# --- Обработчик текстовых сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения в режиме /chat, /roleplay, /translation или /practice."""
    if not is_authorized(update.effective_user.id): return

    user_text = update.message.text
    mode = context.user_data.get('mode')

    # Ограничение истории сообщений для всех режимов, которые ее используют
    max_history_length = 10 # 5 пар сообщений (user + bot) + system-prompt

    if mode == 'chat' or mode == 'roleplay':
        context.user_data['messages'].append({"role": "user", "content": user_text})
        if len(context.user_data['messages']) > max_history_length:
            context.user_data['messages'] = [context.user_data['messages'][0]] + context.user_data['messages'][-max_history_length:]

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=context.user_data['messages'],
                max_tokens=250,
            )
            reply_text = response.choices[0].message.content.strip()
            context.user_data['messages'].append({"role": "assistant", "content": reply_text})
            await update.message.reply_text(reply_text)
            logger.info(f"User {update.effective_user.id} sent a message in {mode} mode.")
        except Exception as e:
            logger.error(f"Error in handle_message for {mode} mode: {e}")
            await update.message.reply_text("An error occurred. Please try again.")

    elif mode == 'translation':
        original_text = context.user_data.get('text_to_translate', 'No text was provided.')
        
        # Очищаем режим перевода после проверки ответа
        context.user_data.clear() 
        
        # prompt = (
        #     f"The original English text was: '{original_text}'. "
        #     f"The user provided this translation: '{user_text}'. "
        #     "Your task is to check the translation. "
        #     "1. First, provide the correct Dutch translation of the text. "
        #     "2. Then, provide a very brief and concise explanation of any errors in ENGLISH. "
        #     "Your entire answer must be short and direct. "
        #     "End your response with a sentence like: 'Try a new translation with /translation [level] [style]!'."
        # )
        # prompt = (
        #     f"The original English text was: '{original_text}'. "
        #     f"The user provided this translation: '{user_text}'. "
        #     "Your task is to check the translation. "
        #     "1. First, provide the correct Dutch translation of the text. "
        #     "2. Then, provide a very brief and concise explanation of any errors in ENGLISH. "
        #     "3. Finally, give a score from 1 to 10 based on the accuracy, grammar, word choice, and naturalness of the translation. "
        #     "The score should be an estimate of how well the user captured the meaning and used correct Dutch. "
        #     "Explain the score briefly in 1 sentence. "
        #     "Your entire answer must be short and direct. "
        #     "End your response with a sentence like: 'Try a new translation with /translation [level] [style]!'."
        # )
        prompt = (
            f"The original English text was: '{original_text}'. "
            f"The user provided this translation: '{user_text}'. "
            "Your task is to check the translation. "
            "1. First, provide a correct Dutch translation (one natural version, not necessarily literal). "
            "2. Then, briefly explain any clear grammar, meaning, or word choice issues in ENGLISH. "
            "3. Finally, give a score from 1 to 10. Base the score on the **accuracy of meaning**, **grammatical correctness**, and **naturalness of the Dutch**, "
            "but **do not penalize for valid synonyms or different phrasing if the translation is still correct and natural**. Only give a score below 6 if the translation contains major errors that seriously affect clarity or correctness. "
            "Explain the score briefly in 1 sentence. "
            "Your entire answer must be short and direct. "
        )

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful Dutch language teacher."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
            )
            reply_text = response.choices[0].message.content.strip()
            await update.message.reply_text(reply_text)
            logger.info(f"User {update.effective_user.id} sent a message in translation mode.")
        except Exception as e:
            logger.error(f"Error in handle_message for translation mode: {e}")
            await update.message.reply_text("An error occurred. Please try again.")

    # --- НОВЫЙ БЛОК ДЛЯ РЕЖИМА PRACTICE ---
    elif mode == 'practice':
        sub_mode = context.user_data.get('practice_sub_mode')
        item = context.user_data.get('practice_item')
        level = context.user_data.get('practice_level')
        original_sentences = context.user_data.get('current_practice_sentences', 'No sentences were provided.')

        if not sub_mode or not original_sentences:
            await update.message.reply_text("Practice session context lost. Please start a new one with `/practice [mode] [item]`.")
            logger.warning(f"User {update.effective_user.id} in practice mode but context lost.")
            context.user_data.clear()
            return

        # Добавляем сообщение пользователя в историю для анализа
        context.user_data['messages'].append({"role": "user", "content": f"My translation for the sentences '{original_sentences}' is: '{user_text}'"})
        
        # Убедимся, что история не слишком длинная перед отправкой
        if len(context.user_data['messages']) > max_history_length:
            context.user_data['messages'] = [context.user_data['messages'][0]] + context.user_data['messages'][-max_history_length:]

        feedback_prompt = (
            f"The original English sentences for {sub_mode} practice (item: '{item}', level: {level}) were: '{original_sentences}'. "
            f"The user provided this Dutch translation: '{user_text}'. "
            "Your task is to check the user's translation. "
            "1. First, provide the correct Dutch translation of the original English sentences. "
            "2. Then, give a very brief and concise explanation of any errors in the user's translation in ENGLISH. "
            "3. Finally, give a score from 1 to 10 based on the accuracy, grammar, word choice, and naturalness of the translation. "
            "The score should be an estimate of how well the user captured the meaning and used correct Dutch. "
            "Explain the score briefly in 1 sentence. "
            "Your entire answer must be short and direct. "
        )

        try:
            # Отправляем всю историю + запрос на проверку
            messages_for_feedback = list(context.user_data['messages']) # Копируем, чтобы добавить временный промпт
            messages_for_feedback.append({"role": "user", "content": feedback_prompt})

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages_for_feedback,
                max_tokens=400,
            )
            reply_text = response.choices[0].message.content.strip()
            context.user_data['messages'].append({"role": "assistant", "content": reply_text}) # Добавляем ответ бота в историю

            await update.message.reply_text(reply_text)
            logger.info(f"User {update.effective_user.id} submitted an answer in practice mode: {sub_mode}, item: {item}.")
        except Exception as e:
            logger.error(f"Error in handle_message for practice mode: {e}")
            await update.message.reply_text("An error occurred while checking your answer. Please try again.")
    
    # --- НОВЫЙ БЛОК ДЛЯ РЕЖИМА EXAM ---
    elif mode == 'exam':
        exam_skill = context.user_data.get('exam_skill')
        exam_task = context.user_data.get('exam_task')

        if not exam_skill or not exam_task:
            await update.message.reply_text(MSG_EXAM_CONTEXT_ERROR)
            context.user_data.clear() # Очищаем на всякий случай
            return

        # Очищаем режим экзамена после получения ответа, чтобы бот вышел из этого режима
        context.user_data.clear()

        # Формируем промпт для оценки ответа пользователя
        review_prompt = ""
        system_role = "You are an NT2 exam evaluator." # Общая роль по умолчанию

        if exam_skill == 'writing':
            review_prompt = (
                f"The user was given the following writing task for NT2 A2 level: "
                f"'{exam_task}'\n\n"
                f"The user's response is: '{user_text}'\n\n"
                "Please evaluate the user's response based on NT2 A2 writing exam criteria. "
                "Focus on grammar, vocabulary, coherence, and task fulfillment. "
                "Provide specific feedback in English followed by a score from 1 to 10. "
                "Also, point out 1-2 main areas for improvement. "
            )
            system_role = "You are a strict but fair NT2 A2 writing exam evaluator."
        elif exam_skill == 'reading':
            # Для чтения, если ответ - это просто выбор буквы, можно проверить напрямую.
            # Если ответ более сложный (например, объяснение), то это будет более "открытое" задание.
            # review_prompt = (
            #     f"The user was given the following reading comprehension task for NT2 A2 level: "
            #     f"'{exam_task}'\n\n"
            #     f"The user's answer is: '{user_text}'\n\n"
            #     "Please evaluate the user's answer. If it's a multiple choice, state if it's correct and why. "
            #     "If it's an open question, assess its accuracy and completeness. "
            #     "Provide feedback in English and a score from 1 to 10. "
            #     "End your response with: 'Probeer een nieuw examen met /exam [vaardigheid]!'"
            # )
            review_prompt = (
                f"The user was given the following reading comprehension task for NT2 A2 level:\n"
                f"'{exam_task}'\n\n"
                f"The user's answer is:\n'{user_text}'\n\n"
                "Please evaluate the user's answer. "
                "If the answer is fully correct, simply say 'Correct' and give a score from 8 to 10 (depending on completeness). "
                "If the answer is incorrect or incomplete, explain briefly why, and give a score from 1 to 7. "
                "Keep feedback short and clear, in English."
            )
            system_role = "You are a precise NT2 A2 reading comprehension evaluator."
        elif exam_skill == 'speaking':
            # Для говорения, поскольку мы получаем текст, нужно оценивать "транскрипцию"
            review_prompt = (
                f"The user was given the following speaking task for NT2 A2 level: "
                f"'{exam_task}'\n\n"
                f"The user's spoken response (as transcribed text) is: '{user_text}'\n\n"
                "Please evaluate this text as if it were a spoken answer for NT2 A2. "
                "Focus on fluency (as much as inferred from text), vocabulary, grammar (if relevant in context). "
                "Provide specific feedback in English and a score from 1 to 10. "
                "Point out 1-2 main areas for improvement. "
            )
            system_role = "You are an empathetic and constructive NT2 A2 speaking exam evaluator."
        elif exam_skill == 'culture':
            review_prompt = (
                f"The user was given the following culture quiz/question for Dutch integration/NT2 A2 level: "
                f"'{exam_task}'\n\n"
                f"The user's answer is: '{user_text}'\n\n"
                "Evaluate the user's answer for accuracy and completeness. "
                "Provide the correct answer if needed. Give feedback in English and a score from 1 to 10. "
            )
            system_role = "You are an informative Dutch culture expert and exam evaluator."

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": review_prompt}
            ],
            max_tokens=600, # Увеличиваем токены для более подробного ответа
        )
        reply_text = response.choices[0].message.content.strip()
        await update.message.reply_text(MSG_EXAM_FEEDBACK_TITLE.format(exam_skill.capitalize(), reply_text), parse_mode="Markdown")
        logger.info(f"User {update.effective_user.id} received feedback for exam task ({exam_skill}).")


    else:
        # Если не в режиме, предлагает начать
        await update.message.reply_text(
            "To get started, use one of the commands: `/chat`, `/roleplay`, `/translation`, `/practice`, `/reading`, `/word`, `/explain`."
        )
        return
        
# --- Основная функция для запуска бота ---
def main() -> None:
    """Запускает бота."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("chat", chat))
    application.add_handler(CommandHandler("roleplay", roleplay))
    application.add_handler(CommandHandler("explain", explain))
    application.add_handler(CommandHandler("reading", reading))
    application.add_handler(CommandHandler("word", word))
    application.add_handler(CommandHandler("translation", translation))
    # ДОБАВЛЕНЫ НОВЫЕ КОМАНДЫ
    application.add_handler(CommandHandler("practice", practice))
    application.add_handler(CommandHandler("more", more))
    application.add_handler(CommandHandler("exam", exam))
    
    # Обработчик для всех текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Бот запущен! Нажмите Ctrl+C, чтобы остановить.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()