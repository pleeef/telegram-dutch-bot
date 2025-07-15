import logging
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
import re
import os
import random # Для выбора случайных предлогов/глаголов/слов по умолчанию
import string

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
                    3. Any useful synonyms or related expressions.
                    4. A brief note on the word's origin or etymology, if known.
                    5. A memory aid (mnemonic) or trick to help remember the word.

                    Format the answer clearly using section headers for each part."""

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

    def get_random_letter():
        return random.choice(string.ascii_uppercase)

    random_letter = get_random_letter()
    
    prompts = {
        #'A': (f"Generate a short, original text of three sentences in English in the style of Lewis Carroll's 'Through the Looking-Glass' (Alice in Wonderland part 2), suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
        #'A': (f"Write a short, simple text in English (three sentences) using vocabulary and grammar at level {level}. The style should be playful and slightly absurd, similar to Lewis Carroll's 'Through the Looking-Glass', but simplified. Use short sentences and avoid complex grammar or puns. No explanation, no quotation marks. Give only the sentences."),
        'A': (f"Write a short, simple text in English (three sentences) using vocabulary and grammar at level {level}. The style should be playful and slightly absurd, similar to Lewis Carroll's 'Through the Looking-Glass', but simplified. Use short sentences and avoid complex grammar or puns. The subject of the sentences must begin with the letter '{random_letter}' (e.g. if 'B', it could be 'Bear', 'Ball', etc). No explanation, no quotation marks. Give only the sentences."),
        #'N': (f"Generate a short, original text of three sentences in English in the style of Vladimir Nabokov's 'Invitation to a Beheading', suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
        'N': (f"Write a short, simple text in English (three sentences) using only {level}-level vocabulary and grammar. The style should resemble the absurd, minimal, and dry tone of Vladimir Nabokov's 'Invitation to a Beheading' (not poetic). Avoid metaphors. The subject of the sentences must begin with the letter '{random_letter}' (e.g. if 'B', it could be 'Bear', 'Ball', etc). No explanation, no quotation marks. Give only the sentences."),
        'F': (f"Generate a short, original text of three sentences in English in the style of a modern fairytale or a young adult fantasy book. The sentences should be suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
        'T': (f"Generate a short, original text of three sentences in English that describes a place or an event, as if it comes from a traveler's journal. The sentences should have a vivid but clear writing style and be suitable for translation to Dutch at level {level}. The text should be related to the topic '{topic}' if possible. Give only the sentences, without any extra explanation or quotation marks."),
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
        
        prompt = (
            f"The original English text was: '{original_text}'. "
            f"The user provided this translation: '{user_text}'. "
            "Your task is to check the translation. "
            "1. First, provide the correct Dutch translation of the text. "
            "2. Then, provide a very brief and concise explanation of any errors in ENGLISH. "
            "Your entire answer must be short and direct. "
            "End your response with a sentence like: 'Try a new translation with /translation [level] [style]!'."
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
            "Your entire answer must be short and direct. "
            "End your response with a clear instruction: 'Ready for the next set? Type /more or start a new practice session with /practice [level] [mode] [item]!'"
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
    
    # Обработчик для всех текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Бот запущен! Нажмите Ctrl+C, чтобы остановить.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()