import json
import random
import os

DATA_FILE = "exercises.json"


def load_exercises(file_path=DATA_FILE):
    """Beolvassa a gyakorlatokat a JSON fájlból, és kezeli a visszamenőleges kompatibilitást."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        exercises = json.load(f)
        
    # Kompatibilitás a régebbi adatszerkezettel rendelkező gyakorlatokhoz
    for ex in exercises:
        if "equipment" not in ex:
            ex["equipment"] = []
        if "type" not in ex:
            ex["type"] = ex.get("categories", [])
            
    return exercises


def save_exercises(exercises, file_path=DATA_FILE):
    """Elmenti a gyakorlatok listáját a JSON fájlba."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(exercises, f, ensure_ascii=False, indent=4)


def add_exercise(name, equipment, ex_type, description="", file_path=DATA_FILE):
    """Új gyakorlatot ad hozzá, ha még nem létezik azonos nevű elem."""
    exercises = load_exercises(file_path)
    
    # Duplikáció ellenőrzése név alapján (kis- és nagybetűktől függetlenül)
    for ex in exercises:
        if ex.get("name", "").strip().lower() == name.strip().lower():
            return None  # Jelzi, hogy a gyakorlat már létezik
    
    new_id = max([e.get("id", 0) for e in exercises], default=0) + 1
    
    new_exercise = {
        "id": new_id,
        "name": name,
        "description": description,
        "equipment": equipment,
        "type": ex_type
    }
    
    exercises.append(new_exercise)
    save_exercises(exercises, file_path)
    return new_exercise


def update_exercise(exercise_id, name, equipment, ex_type, description="", file_path=DATA_FILE):
    """Módosítja egy létező gyakorlat adatait az ID alapján."""
    exercises = load_exercises(file_path)
    updated = False
    for ex in exercises:
        if ex.get("id") == exercise_id:
            ex["name"] = name
            ex["equipment"] = equipment
            ex["type"] = ex_type
            ex["description"] = description
            updated = True
            break
    if updated:
        save_exercises(exercises, file_path)
    return updated


def delete_exercise(exercise_id, file_path=DATA_FILE):
    """Töröl egy gyakorlatot az ID alapján."""
    exercises = load_exercises(file_path)
    initial_len = len(exercises)
    exercises = [ex for ex in exercises if ex.get("id") != exercise_id]
    if len(exercises) < initial_len:
        save_exercises(exercises, file_path)
        return True
    return False


def get_all_equipment(file_path=DATA_FILE):
    """Kigyűjti az összes létező eszköz kategóriát ábécé sorrendben."""
    exercises = load_exercises(file_path)
    eq_set = set()
    for ex in exercises:
        for item in ex.get("equipment", []):
            eq_set.add(item)
    return sorted(list(eq_set))


def get_all_types(file_path=DATA_FILE):
    """Kigyűjti az összes létező típus / izomcsoport kategóriát ábécé sorrendben."""
    exercises = load_exercises(file_path)
    type_set = set()
    for ex in exercises:
        for item in ex.get("type", []):
            type_set.add(item)
    return sorted(list(type_set))


def get_matching_exercises(selected_equipment=None, selected_types=None, file_path=DATA_FILE):
    """
    Kiszűri azokat a gyakorlatokat, amelyek megfelelnek az eszköz ÉS a típus feltételeknek.
    Ha egy szűrő üres, arra a kategóriára nem szűr.
    """
    all_exercises = load_exercises(file_path)
    matching = []

    for ex in all_exercises:
        ex_eq = set(ex.get("equipment", []))
        ex_tp = set(ex.get("type", []))

        # Eszköz szűrés ellenőrzése
        eq_ok = True
        if selected_equipment:
            eq_ok = not set(selected_equipment).isdisjoint(ex_eq)

        # Típus szűrés ellenőrzése
        tp_ok = True
        if selected_types:
            tp_ok = not set(selected_types).isdisjoint(ex_tp)

        if eq_ok and tp_ok:
            matching.append(ex)

    return matching


def generate_workout_by_slots(slot_requirements, file_path=DATA_FILE):
    """Gyakorlatokat generál slot-onként a megadott eszköz és típus szűrők alapján."""
    all_exercises = load_exercises(file_path)
    workout = []
    used_ids = set()

    for req in slot_requirements:
        req_eq = req.get("equipment", [])
        req_tp = req.get("type", [])

        matching = get_matching_exercises(req_eq, req_tp, file_path=file_path)
        available = [ex for ex in matching if ex["id"] not in used_ids]

        if available:
            chosen = random.choice(available)
        elif matching:
            chosen = random.choice(matching)
        else:
            chosen = {
                "id": -1,
                "name": "❌ Nincs találat",
                "description": "Nincs a megadott szűrőknek megfelelő gyakorlat az adatbázisban.",
                "equipment": req_eq,
                "type": req_tp
            }

        workout.append(chosen)
        if chosen["id"] != -1:
            used_ids.add(chosen["id"])

    return workout


def init_sample_data(file_path=DATA_FILE):
    """Kezdő mintaadatok feltöltése, ha üres az adatbázis."""
    if not os.path.exists(file_path) or len(load_exercises(file_path)) == 0:
        add_exercise("Guggolás", ["Saját testsúly"], ["Alsótest", "Láb"], "Saját testsúlyos guggolás vállszéles terpeszben.", file_path)
        add_exercise("Fekvőtámasz", ["Saját testsúly"], ["Felsőtest", "Mell", "Kar"], "Klasszikus fekvőtámasz.", file_path)
        add_exercise("TRX Evezés", ["TRX"], ["Felsőtest", "Hát", "Kar"], "Evezés TRX hevederen törzsfeszítéssel.", file_path)
        add_exercise("Kézisúlyzós vállból nyomás", ["Súlyzó"], ["Felsőtest", "Váll", "Kar"], "Ülve vagy állva nyomás felfelé.", file_path)
        add_exercise("Plank", ["Saját testsúly"], ["Core", "Törzs"], "Alkaron támaszkodás egyenes háttal.", file_path)
        add_exercise("Kettlebell Swing", ["Kettlebell"], ["Alsótest", "Core", "Kardió"], "Dinamikus csípőindítású lendítés kettlebell-lel.", file_path)