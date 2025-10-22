import os
from dotenv import load_dotenv

if os.path.exists(".env"):
    load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AUTHORIZED_USERS = [
    int(uid) for uid in os.environ.get("AUTHORIZED_USERS", "").split(",") if uid
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
WORDS_FILE = os.path.join(DATA_DIR, "frequent_words_2000_5000.csv")

VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
VALID_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']


NUMBERS = [
    "tijd en klok",              # time and clocks
    "datums en dagen",           # dates and days of the week
    "prijzen en geld",           # prices and money
    "telefoonnummers",           # phone numbers
    "huisnummers en adressen",   # house numbers and addresses
    "jaren en leeftijden",       # years and ages
    "temperaturen en weer",      # temperature and weather
    "afstand en snelheid",       # distance and speed
    "hoeveelheden en gewicht",   # quantities and weight
    "pagina's en nummers",       # page, ticket, and seat numbers
    ]


VALID_STYLES = ['A', 'N', 'F', 'T', 'L']

TRANSLATION_STYLE_NAMES = {
    'A': 'Alice',
    'N': 'Nabokov',
    'F': 'Fantasy',
    'T': 'Travel',
    'L': 'Learning'
}
