import json
import random
import os

DATA_FILE = "exercises.json"


def load_exercises(file_path=DATA_FILE):
    """Beolvassa a gyakorlatokat a JSON fájlból."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_exercises(exercises, file_path=DATA_FILE):
    """Elmenti a gyakorlatok listáját a JSON fájlba."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(exercises, f, ensure_ascii=False, indent=4)


def add_exercise(name, categories, description="", file_path=DATA_FILE):
    """Új gyakorlatot ad hozzá az adatbázishoz."""
    exercises = load_exercises(file_path)
    new_id = max([e.get("id", 0) for e in exercises], default=0) + 1
    
    new_exercise = {
        "id": new_id,
        "name": name,
        "description": description,
        "categories": categories
    }
    
    exercises.append(new_exercise)
    save_exercises(exercises, file_path)
    return new_exercise


def get_all_categories(file_path=DATA_FILE):
    """Kigyűjti az összes létező kategóriát ábécé sorrendben."""
    exercises = load_exercises(file_path)
    cats = set()
    for ex in exercises:
        for c in ex.get("categories", []):
            cats.add(c)
    return sorted(list(cats))


def generate_workout(selected_categories, count, file_path=DATA_FILE):
    """Véletlenszerűen kiválaszt 'count' darab gyakorlatot a megadott kategóriákból."""
    all_exercises = load_exercises(file_path)
    
    if not selected_categories:
        matching_exercises = all_exercises
    else:
        selected_set = set(selected_categories)
        matching_exercises = [
            ex for ex in all_exercises 
            if not selected_set.isdisjoint(set(ex.get("categories", [])))
        ]
        
    sample_size = min(count, len(matching_exercises))
    return random.sample(matching_exercises, sample_size)


def get_replacement_exercise(current_workout, selected_categories, file_path=DATA_FILE):
    """Kiválaszt egy olyan új gyakorlatot, ami még nincs benne a jelenlegi edzésben."""
    all_matching = generate_workout(selected_categories, count=999, file_path=file_path)
    current_ids = {ex['id'] for ex in current_workout}
    
    # Olyan gyakorlatok, amik nincsenek a jelenlegi edzésben
    available = [ex for ex in all_matching if ex['id'] not in current_ids]
    
    if available:
        return random.choice(available)
    return None