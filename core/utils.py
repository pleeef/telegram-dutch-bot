import csv
import datetime
import json
import random
from pathlib import Path
from typing import Dict, List, Optional

def load_words_from_csv(path):
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        return [row[0] for row in reader if row]

def generate_random_date_str(start_year=1700, end_year=2030) -> tuple[str, int]:
    """
    Returns a tuple (date_string, year), where date_string is a date string in the format 'DD Month YYYY',
    and year is the selected year (integer).
    """
    today = datetime.date.today()
    random_year = random.randint(start_year, end_year)
    random_date_str = today.strftime(f"%d %B {random_year}")
    current_year = today.year
    return random_date_str, random_year, current_year

def get_random_text_only(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return random.choice(data)["text"]

def get_random_media(path):
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    row = random.choice(rows)
    return row["title"], row["type"]

def get_sentenses_from_json(path, level='B1'):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
        candidates = [w for w in data if w["level"] == level]
        entry = random.choice(candidates)
        word = entry["word"]
        examples = entry["examples"]
        word_translation_en = entry["translation_en"]
        example_sentences_en = [ex["en"] for ex in examples]
        example_sentences_nl = [ex["nl"] for ex in examples]

    return word, word_translation_en, example_sentences_en, example_sentences_nl

# --- Speaking exam (images) helpers ---

def project_root() -> Path:
    """Return absolute project root path (telegram-dutch-bot/)."""
    # core/utils.py -> parents[1] is the project root
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    return project_root() / "data"


def images_json_path() -> Path:
    return data_dir() / "images.json"


def load_speaking_images_tasks() -> List[Dict]:
    """Load speaking image tasks from data/images.json."""
    p = images_json_path()
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def pick_random_task(tasks: List[Dict], exclude_ids: Optional[set] = None) -> Dict:
    """Pick a random task, optionally excluding some task ids to reduce repeats."""
    exclude_ids = exclude_ids or set()
    pool = [t for t in tasks if str(t.get("id")) not in exclude_ids]
    if not pool:
        pool = tasks
    return random.choice(pool)


def image_abs_path(task: Dict) -> Path:
    """Return absolute path to the task image file.

    Expects task['image'] like 'images/1.png' relative to data/.
    """
    return data_dir() / str(task["image"])
