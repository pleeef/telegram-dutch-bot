import csv, datetime, random

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
    return random_date_str, random_year
