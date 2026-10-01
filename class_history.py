"""
Órák és alkalmaik nyilvántartása.

Felépítés (classes.json):
    óra:      {"id", "name", "minutes", "sessions": [...]}
    alkalom:  {"date": "2026-10-07", "workout": [...], "track_ids": [...],
               "playlist_id", "playlist_url"}

Egy alkalmat a dátuma azonosít az órán belül. Az edzést és a playlistet
külön lehet hozzárendelni, ugyanahhoz az alkalomhoz.

Új playlist generálásakor az óra KORÁBBI alkalmait nézzük, és azokat a
számokat választjuk, amiket ez az óra a legrégebben (vagy még soha) nem hallott.
"""

import json
import os
import random

DATA_FILE = "classes.json"

# Az utolsó ennyi alkalom számai egyáltalán nem kerülhetnek be (ha van elég más)
EXCLUDE_LAST_SESSIONS = 2


def load_classes():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        classes = json.load(f)
    # Régebbi mentésekben az alkalmaknak még nem volt "workout" mezője
    for c in classes:
        for s in c["sessions"]:
            s.setdefault("workout", [])
    return classes


def save_classes(classes):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(classes, f, ensure_ascii=False, indent=4)


def get_class(class_id):
    return next((c for c in load_classes() if c["id"] == class_id), None)


def add_class(name, minutes):
    classes = load_classes()
    new_class = {
        "id": max([c["id"] for c in classes], default=0) + 1,
        "name": name,
        "minutes": minutes,
        "sessions": [],
    }
    classes.append(new_class)
    save_classes(classes)
    return new_class


def update_class(class_id, name, minutes):
    classes = load_classes()
    for c in classes:
        if c["id"] == class_id:
            c.update(name=name, minutes=minutes)
    save_classes(classes)


def delete_class(class_id):
    save_classes([c for c in load_classes() if c["id"] != class_id])


# ---------------------------------------------------------------------------
# Alkalmak
# ---------------------------------------------------------------------------
# A dátumokat "ÉÉÉÉ-HH-NN" szövegként tároljuk: így a JSON-ba is beírható,
# és szövegként rendezve is időrendben vannak.

def get_session(cls, day):
    return next((s for s in cls["sessions"] if s["date"] == day), None)


def _session_for_update(cls, day):
    """A megadott napi alkalom; ha még nincs ilyen, létrehozza."""
    session = get_session(cls, day)
    if session is None:
        session = {"date": day, "workout": [], "track_ids": [], "playlist_id": None, "playlist_url": None}
        cls["sessions"].append(session)
        cls["sessions"].sort(key=lambda s: s["date"])
    return session


def assign_workout(class_id, day, workout):
    """
    A generált edzés hozzárendelése egy alkalomhoz. A gyakorlatok teljes
    adatait elmentjük (nem csak az ID-t), így akkor is megmarad, ha később
    egy gyakorlatot törölnek vagy átneveznek.
    """
    classes = load_classes()
    for c in classes:
        if c["id"] == class_id:
            _session_for_update(c, day)["workout"] = workout
    save_classes(classes)


def assign_playlist(class_id, day, track_ids, playlist_id, playlist_url):
    """
    Playlist hozzárendelése egy alkalomhoz.
    Visszaadja a lecserélt régi playlist ID-ját (ha volt), hogy törölni lehessen.
    """
    classes = load_classes()
    old_playlist_id = None
    for c in classes:
        if c["id"] == class_id:
            session = _session_for_update(c, day)
            old_playlist_id = session["playlist_id"]
            session.update(track_ids=track_ids, playlist_id=playlist_id, playlist_url=playlist_url)
    save_classes(classes)
    return old_playlist_id


def forget_playlist(class_id, playlist_id):
    """A Spotify playlist törlése után: a számok listája marad, csak a link törlődik."""
    classes = load_classes()
    for c in classes:
        if c["id"] == class_id:
            for s in c["sessions"]:
                if s["playlist_id"] == playlist_id:
                    s["playlist_id"] = None
                    s["playlist_url"] = None
    save_classes(classes)


def delete_session(class_id, day):
    classes = load_classes()
    for c in classes:
        if c["id"] == class_id:
            c["sessions"] = [s for s in c["sessions"] if s["date"] != day]
    save_classes(classes)


# ---------------------------------------------------------------------------
# Playlist összeállítás
# ---------------------------------------------------------------------------

def sessions_since_played(cls, before_day):
    """
    {track_id: hány alkalommal ezelőtt szólt utoljára}, a before_day előtti
    alkalmak alapján. 0 = az előző alkalmon, 1 = az azelőttin, stb.
    Ami nincs benne, az ezen az órán még nem szólt.
    """
    earlier = [s for s in cls["sessions"] if s["date"] < before_day]
    result = {}
    for ago, session in enumerate(reversed(earlier)):
        for tid in session["track_ids"]:
            result.setdefault(tid, ago)  # csak a legutóbbi előfordulás számít
    return result


def build_session(cls, day, pool, new_tracks=(), n_new=0):
    """
    Összeállít egy óra-playlistet a megadott napra.

    cls: az óra (load_classes() egy eleme)
    pool: a fő playlist számai
    new_tracks: felfedezett, még nem hallott számok
    n_new: ebből hány kerüljön bele

    Visszaad: számok listája, mindegyikben "is_new" és "last_played" mezővel.
    """
    target_ms = cls["minutes"] * 60 * 1000
    history = sessions_since_played(cls, day)
    played_before = len({s["date"] for s in cls["sessions"] if s["date"] < day})

    # Pontozás: minél régebben szólt, annál jobb. Ami még soha, az a legjobb.
    # A kis véletlen azért kell, hogy az azonos pontú számok sorrendje
    # óráról órára változzon.
    never = played_before + 1

    def priority(t):
        return history.get(t["id"], never) + random.random()

    fresh = [t for t in pool if history.get(t["id"], never) >= EXCLUDE_LAST_SESSIONS]
    recent = [t for t in pool if history.get(t["id"], never) < EXCLUDE_LAST_SESSIONS]
    ordered = sorted(fresh, key=priority, reverse=True) + sorted(recent, key=priority, reverse=True)

    # Az új számok előre kerülnek, a maradék időt a régiek töltik ki
    chosen_new = list(new_tracks)[:n_new]
    chosen = []
    total = 0
    for t in chosen_new + ordered:
        if total >= target_ms:
            break
        if any(c["id"] == t["id"] for c in chosen):
            continue
        chosen.append(t)
        total += t["duration_ms"]

    new_ids = {t["id"] for t in chosen_new}
    result = [
        {**t, "is_new": t["id"] in new_ids, "last_played": history.get(t["id"])}
        for t in chosen
    ]
    # Végül megkeverjük, hogy az új számok ne mind az elején legyenek
    random.shuffle(result)
    return result
