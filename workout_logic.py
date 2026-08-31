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
    
    # Egyedi ID generálása
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


def generate_workout(selected_categories, count, file_path=DATA_FILE):
    """
    Véletlenszerűen kiválaszt 'count' darab gyakorlatot, amelyek 
    tartalmazzák a megadott kategóriák legalább egyikét.
    """
    all_exercises = load_exercises(file_path)
    
    # Szűrés: az a gyakorlat felel meg, aminek van közös kategóriája a kiválasztottakkal
    matching_exercises = []
    selected_set = set(selected_categories)
    
    for ex in all_exercises:
        ex_categories = set(ex.get("categories", []))
        if not selected_set.isdisjoint(ex_categories):  # Ha van közös kategória
            matching_exercises.append(ex)

    # Ha kevesebb a találat, mint a kért szám, akkor az összes találatot visszaadjuk
    sample_size = min(count, len(matching_exercises))
    return random.sample(matching_exercises, sample_size)


# --- KIS TESZT ÉS MINTA ADATOK FELTÖLTÉSE ---
if __name__ == "__main__":
    # Ha még nincs adatbázis, feltöltjük néhány minta gyakorlattal
    if not os.path.exists(DATA_FILE) or len(load_exercises()) == 0:
        print("Minta adatok feltöltése...")
        add_exercise("Guggolás", ["Láb", "Saját testsúly"], "Saját testsúlyos guggolás vállszéles terpeszben.")
        add_exercise("Fekvőtámasz", ["Mell", "Kar", "Saját testsúly"], "Klasszikus fekvőtámasz.")
        add_exercise("Kitörés", ["Láb"], "Alternáló kitörések előre.")
        add_exercise("Plank", ["Törzs", "Saját testsúly"], "Alkaron támaszkodás egyenes háttal.")
        add_exercise("Kézisúlyzós vállból nyomás", ["Váll", "Kar", "Súlyzós"], "Ülve vagy állva nyomás felfelé.")
        add_exercise("Barpí (Négyütemű)", ["Kardió", "Saját testsúly"], "Dinamikus teljes testgyakorlat.")

    print("\n--- Összes meglévő gyakorlat ---")
    for ex in load_exercises():
        print(f"[{ex['id']}] {ex['name']} - Kategóriák: {', '.join(ex['categories'])}")

    print("\n--- Köredzés generálás teszt (2 db 'Láb' vagy 'Kardió' gyakorlat) ---")
    workout = generate_workout(selected_categories=["Láb", "Kardió"], count=2)
    for i, ex in enumerate(workout, 1):
        print(f"{i}. {ex['name']} ({', '.join(ex['categories'])})")