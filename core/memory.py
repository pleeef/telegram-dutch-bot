import json, os, datetime

class MemoryManager:
    def __init__(self, filepath):
        self.filepath = filepath

    def load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"dictate": {}, "translation": {}}

    def save(self, memory):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)

    def add_sentence(self, mode, sentence):
        memory = self.load()
        today = str(datetime.date.today())
        memory.setdefault(mode, {}).setdefault(today, [])
        if sentence not in memory[mode][today]:
            memory[mode][today].append(sentence)
        self.save(memory)

    def get_recent_sentences(self, mode, days=7):
        memory = self.load()
        if mode not in memory:
            return []
        today = datetime.date.today()
        result = []
        for date_str, sentences in memory[mode].items():
            try:
                date_obj = datetime.date.fromisoformat(date_str)
                if (today - date_obj).days <= days:
                    result.extend(sentences)
            except ValueError:
                continue
        return result
